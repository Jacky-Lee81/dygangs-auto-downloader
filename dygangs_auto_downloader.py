#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dygangs.net 自动下载器

此脚本用于从 dygangs.net 搜索电视剧和电影，并自动将下载任务添加到Transmission中。
电影下载到 /vol1/1000/downloads/movies
电视剧下载到 /vol1/1000/downloads/tv
"""

import re
import sys
import json
import urllib.parse
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup


class DygangsAutoDownloader:
    def __init__(self, transmission_url: str = "http://192.168.20.27:9091/transmission/rpc", 
                 username: str = "admin", password: str = "123456"):
        self.base_url = "https://www.dygangs.net"
        self.transmission_url = transmission_url
        self.session = requests.Session()
        self.session.auth = (username, password)
        # 默认 headers 与重试策略，增加鲁棒性
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) DygangsAutoDownloader/1.0'
        })
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=(500, 502, 503, 504))
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.transmission_session_id = None
        self.dry_run = False
        
    def get_transmission_session_id(self):
        """获取Transmission的会话ID"""
        try:
            # 使用一次空的 POST 请求以触发 Transmission 返回 409 并携带会话ID
            headers = {"Content-Type": "application/json"}
            response = self.session.post(self.transmission_url, headers=headers, json={})
            if response.status_code == 409:
                # 从响应头中获取新的会话ID
                self.transmission_session_id = response.headers.get('X-Transmission-Session-Id')
                return True
            # 如果返回200则说明不需要会话ID或认证已通过
            if response.status_code == 200:
                return True
            return False
        except Exception as e:
            print(f"获取Transmission会话ID失败: {e}")
            return False
    
    def add_to_transmission(self, magnet_uri: str, download_dir: str, filename: str = ""):
        """添加磁力链接到Transmission下载"""
        if getattr(self, 'dry_run', False):
            print(f"[dry-run] 将添加到 Transmission: {filename} -> {magnet_uri} (dir: {download_dir})")
            return True
        # 确保有会话ID（如果需要）
        if not self.transmission_session_id:
            self.get_transmission_session_id()

        headers = {"Content-Type": "application/json"}
        if self.transmission_session_id:
            headers["X-Transmission-Session-Id"] = self.transmission_session_id

        payload = {
            "method": "torrent-add",
            "arguments": {
                "filename": magnet_uri,
                "download-dir": download_dir
            }
        }

        # 尝试发送请求，若返回409则更新会话ID并重试一次
        try:
            response = self.session.post(self.transmission_url, headers=headers, json=payload)
            if response.status_code == 409:
                # 更新会话ID并重试
                new_id = response.headers.get('X-Transmission-Session-Id')
                if new_id:
                    self.transmission_session_id = new_id
                    headers["X-Transmission-Session-Id"] = new_id
                    response = self.session.post(self.transmission_url, headers=headers, json=payload)

            # 如果仍然不是200，打印错误并返回
            if response.status_code != 200:
                print(f"Transmission 返回非预期状态码: {response.status_code}")
                return False

            result = response.json()
            if result.get("result") == "success":
                print(f"成功添加下载任务: {filename}")
                return True
            else:
                print(f"添加下载任务失败: {result.get('result')}")
                return False
        except Exception as e:
            print(f"添加下载任务时出错: {e}")
            return False
    
    def search_content(self, keyword: str) -> List[Dict[str, str]]:
        """在dygangs.net搜索内容"""
        search_url = f"{self.base_url}/e/search/index.php"

        # 表单字段，优先使用 POST 提交以获得 searchid（若存在）
        form = {
            'keyboard': keyword,
            'show': 'title',
            'tempid': '1',
            'tbname': 'article'
        }

        try:
            # 先访问首页获取 cookies 与初始 headers
            try:
                self.session.get(self.base_url, timeout=5)
            except Exception:
                pass

            # 尝试使用 gb2312 编码提交表单（目标站点使用 gb2312）
            try:
                encoded = urllib.parse.urlencode(form, encoding='gb2312').encode('gb2312')
                headers = {'Referer': self.base_url, 'Content-Type': 'application/x-www-form-urlencoded; charset=gb2312'}
                resp = self.session.post(search_url, data=encoded, headers=headers, timeout=10)
            except Exception:
                # 回退到默认提交
                resp = self.session.post(search_url, data=form, timeout=10)
            resp.raise_for_status()

            # 处理编码：尽量使用 requests 推断的编码以正确显示中文
            try:
                resp.encoding = resp.apparent_encoding
            except Exception:
                pass

            text = resp.text

            # 如果页面包含 searchid 跳转链接，跟进结果页
            m = re.search(r'searchid=(\d+)', text)
            result_pages = []
            if m:
                searchid = m.group(1)
                result_url = urllib.parse.urljoin(self.base_url, f"/e/search/result/?searchid={searchid}")
                result_pages.append(result_url)
            else:
                # 有些站点会直接在 POST 返回中带有结果页面，直接解析当前页面
                result_pages.append(resp.url)

            results = []
            seen = set()

            href_pattern = re.compile(r'/(dsj|ys|bd|gp|zy)/[^"\'>]+')

            def normalize(s: str) -> str:
                return re.sub(r'\s+', '', (s or '')).lower()

            nk = normalize(keyword)

            for page in result_pages:
                try:
                    r2 = self.session.get(page, timeout=10)
                    r2.raise_for_status()
                    try:
                        r2.encoding = r2.apparent_encoding
                    except Exception:
                        pass
                    # 使用 bytes 解析以由 bs4 根据 meta 正确识别编码
                    soup = BeautifulSoup(r2.content, 'html.parser')

                    # 优先使用页面中显示结果的选择器（class=c2 为标题链接）
                    for a in soup.select('a.c2'):
                        href = a.get('href')
                        if not href:
                            continue
                        full_url = href if href.startswith('http') else urllib.parse.urljoin(self.base_url, href)
                        if full_url in seen:
                            continue

                        title = (a.get_text(strip=True) or '').strip()
                        if not title:
                            parent = a.parent
                            title = parent.get_text(strip=True) if parent else ''

                        if nk and nk not in normalize(title):
                            continue

                        content_type = 'tv' if '/dsj/' in href else 'movie'
                        results.append({'title': title, 'url': full_url, 'type': content_type})
                        seen.add(full_url)
                except Exception:
                    continue

            return results
            
        except Exception as e:
            print(f"搜索过程中出现错误: {e}")
            return []
    
    def extract_magnets_from_page(self, url: str) -> List[Dict[str, str]]:
        """从内容详情页提取磁力链接"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            magnets = []
            seen = set()

            # 优先使用结构化 HTML 中的 <a href^="magnet:">
            soup = BeautifulSoup(response.content, 'html.parser')

            # 先找常见标题作为文件名备选
            title_candidates = []
            h1 = soup.find('h1')
            if h1:
                title_candidates.append(h1.get_text(strip=True))
            og = soup.find('meta', property='og:title')
            if og and og.get('content'):
                title_candidates.append(og.get('content'))
            if soup.title and soup.title.string:
                title_candidates.append(soup.title.string.strip())

            def choose_title():
                for t in title_candidates:
                    if t:
                        return t
                return 'Unknown'

            for a in soup.find_all('a', href=re.compile(r'^magnet:')):
                href = a['href'].strip()
                if href in seen:
                    continue
                filename = a.get_text(strip=True) or a.get('title') or choose_title()
                filename = re.sub(r'\s+', ' ', filename).strip()
                magnets.append({'magnet': href, 'filename': filename})
                seen.add(href)

            # 其次，从文本中用更严格的正则查找并去重
            magnet_pattern = re.compile(r'(magnet:\?xt=[^"\'\s<>]+)')
            for m in magnet_pattern.findall(response.text):
                if m in seen:
                    continue
                idx = response.text.find(m)
                context = response.text[max(0, idx-200): idx+200]
                fn = re.search(r'([\u4e00-\u9fff\w \-_.()]{3,80})', context)
                filename = fn.group(1).strip() if fn else choose_title()
                magnets.append({'magnet': m, 'filename': filename})
                seen.add(m)

            # 清理：统一实体、解码、优先使用 dn 参数作为文件名、再次去重并过滤不合理条目
            import html
            clean = []
            final_seen = set()
            for item in magnets:
                mag = item.get('magnet', '')
                # 清理 HTML 实体
                mag = html.unescape(mag)
                mag = mag.replace('&amp;', '&')

                # 尝试解析 dn 参数作为文件名
                fn = item.get('filename') or ''
                try:
                    q = urllib.parse.urlparse(mag).query
                    params = urllib.parse.parse_qs(q)
                    if 'dn' in params and params['dn']:
                        # 取第一个 dn 并解码百分号编码
                        dn = params['dn'][0]
                        dn = urllib.parse.unquote(dn)
                        fn = dn
                except Exception:
                    pass

                # 清理文件名空白与 HTML 实体
                fn = html.unescape(fn).strip()

                # 过滤不合理的文件名
                if not fn or len(fn) < 3 or fn.lower().endswith('.html') or fn.lower() == 'unknown':
                    # 回退到标题或跳过
                    fn = choose_title()
                    if not fn or fn.lower() == 'unknown':
                        continue

                if mag in final_seen:
                    continue
                final_seen.add(mag)
                clean.append({'magnet': mag, 'filename': fn})

            return clean
            
        except Exception as e:
            print(f"提取磁力链接时出现错误: {e}")
            return []

    def save_page(self, url: str, out_path: Optional[str] = None, timeout: int = 10) -> Optional[str]:
        """将指定 URL 的页面内容保存到本地文件。

        如果未指定 `out_path`，将根据主机与路径生成一个默认文件名。
        返回保存的文件路径，出错返回 None。
        """
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; DygangsAutoDownloader/1.0)"}
            resp = self.session.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()

            content = resp.content

            if not out_path:
                parsed = urllib.parse.urlparse(url)
                path = parsed.path.strip('/') or 'index'
                # 把路径里的 / 转为下划线，去掉查询与片段
                safe_path = path.replace('/', '_')
                filename = f"{parsed.netloc}_{safe_path}.html"
                out_path = os.path.abspath(filename)

            # 确保目录存在
            out_dir = os.path.dirname(out_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            with open(out_path, 'wb') as f:
                f.write(content)

            print(f"已保存网页到: {out_path}")
            return out_path
        except Exception as e:
            print(f"保存页面时出错: {e}")
            return None
    
    def download_from_url(self, url: str, content_type: str = "movie"):
        """
        直接从URL下载内容
        content_type: "movie", "tv"
        """
        print(f"正在处理页面: {url}")
        
        # 确定下载目录
        if content_type == "movie":
            download_dir = "/vol1/1000/downloads/movies"
        else:
            download_dir = "/vol1/1000/downloads/tv"
        
        # 提取磁力链接
        magnets = self.extract_magnets_from_page(url)
        
        if not magnets:
            print(f"  在页面中未找到磁力链接")
            return False
        
        print(f"  找到 {len(magnets)} 个磁力链接")
        
        # 添加到Transmission
        for magnet_info in magnets:
            magnet_uri = magnet_info['magnet']
            filename = magnet_info['filename']
            
            print(f"  正在添加到Transmission: {filename}")
            success = self.add_to_transmission(magnet_uri, download_dir, filename)
            
            if success:
                print(f"    ✓ 成功添加: {filename}")
            else:
                print(f"    ✗ 添加失败: {filename}")
        
        return True
    
    def download_content(self, keyword: str, content_type: str = "auto"):
        """
        搜索并下载内容
        content_type: "auto", "movie", "tv"
        """
        print(f"正在搜索: {keyword}")
        
        # 搜索内容
        search_results = self.search_content(keyword)
        
        if not search_results:
            print(f"未找到关于 '{keyword}' 的相关内容")
            return False
        
        print(f"找到 {len(search_results)} 个相关结果:")
        for i, result in enumerate(search_results):
            print(f"  {i+1}. {result['title']} ({result['type']}) - {result['url']}")
        
        # 处理每个搜索结果
        for result in search_results:
            print(f"\n正在处理: {result['title']}")
            
            # 确定下载目录
            if content_type == "movie" or result['type'] == "movie":
                download_dir = "/vol1/1000/downloads/movies"
            elif content_type == "tv" or result['type'] == "tv":
                download_dir = "/vol1/1000/downloads/tv"
            else:
                # 自动判断类型
                download_dir = "/vol1/1000/downloads/tv" if result['type'] == "tv" else "/vol1/1000/downloads/movies"
            
            # 提取磁力链接
            magnets = self.extract_magnets_from_page(result['url'])
            
            if not magnets:
                print(f"  在页面中未找到磁力链接")
                continue
            
            print(f"  找到 {len(magnets)} 个磁力链接")
            
            # 添加到Transmission
            for magnet_info in magnets:
                magnet_uri = magnet_info['magnet']
                filename = magnet_info['filename']
                
                print(f"  正在添加到Transmission: {filename}")
                success = self.add_to_transmission(magnet_uri, download_dir, filename)
                
                if success:
                    print(f"    ✓ 成功添加: {filename}")
                else:
                    print(f"    ✗ 添加失败: {filename}")
        
        return True


def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  搜索模式: python dygangs_auto_downloader.py <搜索关键词> [类型:movie|tv]")
        print("  URL模式: python dygangs_auto_downloader.py --url <页面URL> [类型:movie|tv]")
        print("示例:")
        print("  python dygangs_auto_downloader.py '夜色正浓'")
        print("  python dygangs_auto_downloader.py '速度与激情' movie")
        print("  python dygangs_auto_downloader.py --url 'https://www.dygangs.net/ys/' movie")
        return
    
    # 检查 dry-run 标志
    dry_run_flag = '--dry-run' in sys.argv
    # 移除 dry-run 参数以免影响后续参数解析
    if dry_run_flag:
        sys.argv = [a for a in sys.argv if a != '--dry-run']

    downloader = DygangsAutoDownloader()
    if dry_run_flag:
        downloader.dry_run = True
    
    # 检查是否是URL模式
    if sys.argv[1] == "--url":
        if len(sys.argv) < 3:
            print("错误: --url 模式需要提供页面URL")
            return
        url = sys.argv[2]
        content_type = sys.argv[3] if len(sys.argv) > 3 else "movie"
        downloader.download_from_url(url, content_type)
    elif sys.argv[1] == "--save-url":
        # 单独保存页面到本地： python dygangs_auto_downloader.py --save-url <url> [out_path]
        if len(sys.argv) < 3:
            print("错误: --save-url 需要提供页面URL")
            return
        url = sys.argv[2]
        out_path = sys.argv[3] if len(sys.argv) > 3 else None
        downloader.save_page(url, out_path)
    else:
        keyword = sys.argv[1]
        content_type = sys.argv[2] if len(sys.argv) > 2 else "auto"
        downloader.download_content(keyword, content_type)


if __name__ == "__main__":
    main()