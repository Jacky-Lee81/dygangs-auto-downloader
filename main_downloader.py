#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主下载程序

功能：
1. 下载HTML文件
2. 使用parse_local_html.py解析电影或电视剧
3. 调用自动下载
"""

import urllib.parse
import sys
import os
import time
import re
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dygangs_auto_downloader import DygangsAutoDownloader


class MainDownloader:
    """
    主下载程序类
    """
    
    def __init__(self):
        """
        初始化主下载程序
        """
        self.downloader = DygangsAutoDownloader()
        self.verbose = False
    
    def download_html(self, url: str, output: Optional[str] = None) -> Optional[str]:
        """
        下载HTML文件
        
        Args:
            url: 网页URL
            output: 保存路径
            
        Returns:
            保存的文件路径
        """
        if self.verbose:
            print(f"正在下载网页: {url}")
        
        # 生成默认保存路径
        if not output:
            timestamp = int(time.time())
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc
            path = parsed.path.strip('/') or 'index'
            safe_path = path.replace('/', '_')
            filename = f"{domain}_{safe_path}_{timestamp}.html"
            output = os.path.join('data', 'pages', filename)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
        
        # 下载网页
        saved_path = self.downloader.save_page(url, output)
        
        if saved_path:
            if self.verbose:
                print(f"网页已保存到: {saved_path}")
            return saved_path
        else:
            print(f"下载网页失败: {url}")
            return None
    
    def _sort_magnets_by_quality(self, magnets: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        按码率和质量排序磁力链接
        
        Args:
            magnets: 磁力链接列表
            
        Returns:
            排序后的磁力链接列表
        """
        def get_quality_score(magnet: Dict[str, str]) -> int:
            """
            计算磁力链接的质量得分
            """
            score = 0
            original_filename = magnet.get('filename', '')
            filename = original_filename.lower()
            
            # 按分辨率评分
            if '2160p' in filename or '4k' in filename:
                score += 100
            elif '1080p' in filename:
                score += 80
            elif '720p' in filename:
                score += 60
            elif '480p' in filename:
                score += 40
            
            # 按码率评分
            if '高码' in original_filename or 'high' in filename:
                score += 50
            if '120fps' in filename:
                score += 40
            if '60fps' in filename:
                score += 30
            
            # 按其他质量指标评分
            if '蓝光' in original_filename or 'bluray' in filename:
                score += 30
            if 'hdr' in filename:
                score += 20
            if '原盘' in original_filename or 'remux' in filename:
                score += 40
            
            # 优先下载全集链接（电视剧）
            if '全集' in original_filename:
                score += 150
            
            # 按文件大小评分（简单判断）
            if 'gb' in filename:
                import re
                size_match = re.search(r'\d+(\.\d+)?\s*gb', filename)
                if size_match:
                    try:
                        size = float(size_match.group(0).replace('gb', '').strip())
                        score += int(size * 2)  # 每GB加2分
                    except:
                        pass
            
            # 调试信息
            if self.verbose:
                print(f"调试: 文件名: '{original_filename}', 得分: {score}")
            
            return score
        
        # 按质量得分降序排序
        sorted_magnets = sorted(magnets, key=get_quality_score, reverse=True)
        
        # 打印排序结果（如果启用详细输出）
        if self.verbose:
            print("磁力链接排序结果:")
            for i, magnet in enumerate(sorted_magnets[:5], 1):
                filename = magnet.get('filename', '')
                score = get_quality_score(magnet)
                print(f"{i}. {filename} (得分: {score})")
        
        return sorted_magnets
    
    def parse_html(self, html_file: str, keyword: str) -> List[Tuple[str, str]]:
        """
        解析HTML文件，提取匹配关键词的电影/电视剧
        
        Args:
            html_file: HTML文件路径
            keyword: 搜索关键词
            
        Returns:
            匹配项列表 [(标题, URL)]
        """
        if self.verbose:
            print(f"正在解析HTML文件: {html_file}")
            print(f"搜索关键词: {keyword}")
        
        matches = []
        
        try:
            # 读取文件内容
            with open(html_file, 'rb') as f:
                data = f.read()
            
            # 尝试不同的编码解码
            encodings = ['utf-8', 'gb2312', 'gbk', 'iso-8859-1']
            decoded_data = None
            for encoding in encodings:
                try:
                    decoded_data = data.decode(encoding)
                    break
                except:
                    continue
            
            if not decoded_data:
                # 如果所有编码都失败，使用默认解码
                decoded_data = data.decode('utf-8', errors='ignore')
            
            # 使用BeautifulSoup解析
            soup = BeautifulSoup(decoded_data, 'html.parser')
            
            # 搜索链接
            link_selectors = [
                'a.c2',  # 原始选择器
                'a.classlinkclass',  # 新的选择器
                'a[href]',  # 所有链接
                'a.title',  # 标题链接
                'a[class*="link"]',  # 包含link的类
                'a[class*="title"]',  # 包含title的类
            ]
            
            seen = set()
            
            for selector in link_selectors:
                for a in soup.select(selector):
                    title = a.get_text(strip=True)
                    if not title:
                        continue
                    
                    # 检查是否匹配关键词
                    # 尝试不同的编码和匹配方式
                    matched = False
                    try:
                        # 调试信息
                        if self.verbose:
                            print(f"调试: 检查标题: '{title}'")
                            print(f"调试: 关键词: '{keyword}'")
                        
                        # 直接匹配
                        if keyword in title:
                            matched = True
                            if self.verbose:
                                print("调试: 直接匹配成功")
                        # 不区分大小写匹配
                        elif keyword.lower() in title.lower():
                            matched = True
                            if self.verbose:
                                print("调试: 不区分大小写匹配成功")
                        # 移除方括号内容后匹配
                        elif keyword in re.sub(r'\[.*?\]', '', title):
                            matched = True
                            if self.verbose:
                                print("调试: 移除方括号后匹配成功")
                        # 移除方括号内容后不区分大小写匹配
                        elif keyword.lower() in re.sub(r'\[.*?\]', '', title).lower():
                            matched = True
                            if self.verbose:
                                print("调试: 移除方括号后不区分大小写匹配成功")
                        # 更宽松的匹配：只要标题中包含关键词的每个字符
                        elif all(char in title for char in keyword):
                            matched = True
                            if self.verbose:
                                print("调试: 宽松匹配成功")
                        # 特殊处理：对于"夜色正浓"，直接检查标题是否包含"夜色正浓"
                        elif keyword == "夜色正浓" and "夜色正浓" in title:
                            matched = True
                            if self.verbose:
                                print("调试: 特殊处理匹配成功")
                    except Exception as e:
                        if self.verbose:
                            print(f"调试: 匹配时出错: {e}")
                        pass
                    
                    if matched:
                        href = a.get('href')
                        if not href:
                            continue
                        
                        # 去重
                        if href in seen:
                            continue
                        seen.add(href)
                        
                        # 构建完整URL
                        full_url = href if href.startswith('http') else urllib.parse.urljoin('https://www.dygangs.net', href)
                        matches.append((title, full_url))
                        if self.verbose:
                            print(f"调试: 添加匹配项: '{title}' -> '{full_url}'")
            
            if self.verbose:
                print(f"找到 {len(matches)} 个匹配项")
            
        except Exception as e:
            print(f"解析HTML文件失败: {e}")
        
        return matches
    
    def auto_download(self, title: str, url: str, content_type: str = "movie", dry_run: bool = False, max_magnets: int = 3) -> bool:
        """
        自动下载电影/电视剧
        
        Args:
            title: 标题
            url: 详情页URL
            content_type: 内容类型 (movie/tv)
            dry_run: 是否为dry-run模式
            max_magnets: 最大处理的磁力链接数
            
        Returns:
            是否下载成功
        """
        # 对于电影类型，只处理一个磁力链接（得分最高的那个）
        if content_type == "movie":
            max_magnets = 1
        if self.verbose:
            print(f"\n正在处理: {title}")
            print(f"URL: {url}")
            print(f"内容类型: {content_type}")
            print(f"Dry-run模式: {dry_run}")
            print(f"最大磁力链接数: {max_magnets}")
        
        # 设置dry-run模式
        original_dry_run = self.downloader.dry_run
        self.downloader.dry_run = dry_run
        
        try:
            # 提取磁力链接
            magnets = self.downloader.extract_magnets_from_page(url)
            
            if not magnets:
                print(f"未找到磁力链接: {title}")
                return False
            
            # 按码率排序磁力链接（电影和电视剧都排序）
            magnets = self._sort_magnets_by_quality(magnets)
            if self.verbose:
                print("已按码率排序磁力链接")
            
            if self.verbose:
                print(f"提取到 {len(magnets)} 个磁力链接")
                print(f"将处理前 {min(max_magnets, len(magnets))} 个磁力链接")
            
            # 确定下载目录
            if content_type == "movie":
                download_dir = "/vol1/1000/downloads/movies"
            else:
                download_dir = "/vol1/1000/downloads/tv"
            
            # 添加到Transmission
            success_count = 0
            for magnet_info in magnets[:max_magnets]:  # 只下载指定数量的磁力链接
                magnet_uri = magnet_info['magnet']
                filename = magnet_info['filename']
                
                if self.verbose:
                    print(f"\n添加到Transmission: {filename}")
                    print(f"磁力链接: {magnet_uri[:100]}...")
                
                if not dry_run:
                    success = self.downloader.add_to_transmission(magnet_uri, download_dir, filename)
                    if success:
                        success_count += 1
                        print(f"✅ 成功添加: {filename}")
                    else:
                        print(f"❌ 添加失败: {filename}")
                else:
                    print(f"[dry-run] 将要添加: {filename}")
                    success_count += 1
            
            if success_count > 0:
                print(f"\n✅ 成功处理 {success_count} 个磁力链接")
                return True
            else:
                print("\n❌ 所有磁力链接添加失败")
                return False
                
        finally:
            # 恢复原始dry-run设置
            self.downloader.dry_run = original_dry_run
    
    def run(self, url: str, keyword: str, output: Optional[str] = None, 
            content_type: str = "movie", dry_run: bool = False, verbose: bool = False, 
            max_magnets: int = 3, max_matches: int = 3):
        """
        运行完整流程
        
        Args:
            url: 网页URL
            keyword: 搜索关键词
            output: HTML保存路径
            content_type: 内容类型
            dry_run: 是否为dry-run模式
            verbose: 是否启用详细输出
            max_magnets: 最大处理的磁力链接数
            max_matches: 最大处理的匹配项数
        """
        self.verbose = verbose
        
        print("=== 主下载程序 ===")
        print(f"URL: {url}")
        print(f"关键词: {keyword}")
        print(f"内容类型: {content_type}")
        print(f"Dry-run: {dry_run}")
        print(f"详细输出: {verbose}")
        print(f"最大磁力链接数: {max_magnets}")
        print(f"最大匹配项数: {max_matches}")
        print()
        
        # 步骤1: 下载HTML文件
        print("步骤1: 下载HTML文件")
        html_file = self.download_html(url, output)
        if not html_file:
            print("❌ 下载失败，程序退出")
            return False
        print("✅ 下载完成")
        print()
        
        # 步骤2: 解析HTML文件
        print("步骤2: 解析HTML文件")
        matches = self.parse_html(html_file, keyword)
        
        # 如果没有找到匹配项，尝试下一页（支持电影和电视剧类型）
        if not matches and (content_type == "tv" or content_type == "movie"):
            print("❌ 未找到匹配项，尝试下一页...")
            # 构建下一页URL
            if url.endswith('/'):
                next_page_url = url + "index_2.htm"
            else:
                next_page_url = url.rsplit('/', 1)[0] + "/index_2.htm"
            print(f"尝试下载下一页: {next_page_url}")
            # 下载下一页
            next_html_file = self.download_html(next_page_url)
            if next_html_file:
                print("✅ 下一页下载完成，开始解析...")
                # 解析下一页
                matches = self.parse_html(next_html_file, keyword)
                if not matches:
                    print("❌ 下一页也未找到匹配项，程序退出")
                    return False
                print(f"✅ 在下一页找到 {len(matches)} 个匹配项")
            else:
                print("❌ 下载下一页失败，程序退出")
                return False
        elif not matches:
            print("❌ 未找到匹配项，程序退出")
            return False
        else:
            print(f"✅ 找到 {len(matches)} 个匹配项")
        
        # 显示匹配项
        for i, (title, match_url) in enumerate(matches[:max_matches], 1):
            print(f"{i}. {title} - {match_url}")
        print()
        
        # 步骤3: 自动下载
        print("步骤3: 自动下载")
        success = False
        
        # 处理指定数量的匹配项
        for i, (title, match_url) in enumerate(matches[:max_matches], 1):
            print(f"\n处理第 {i} 个匹配项:")
            if self.auto_download(title, match_url, content_type, dry_run, max_magnets):
                success = True
                # 如果成功，只处理第一个匹配项
                break
        
        if success:
            print("\n=== 下载完成 ===")
            print("✅ 成功下载电影/电视剧")
        else:
            print("\n=== 下载失败 ===")
            print("❌ 未能成功下载电影/电视剧")
        
        return success


def main():
    """
    主函数
    """
    if len(sys.argv) < 3:
        print("使用方法:")
        print("  python3 main_downloader.py <url> <keyword> [选项]")
        print("选项:")
        print("  --type <类型>          指定内容类型: movie, tv (默认: movie)")
        print("  --output <路径>        指定HTML文件保存路径")
        print("  --dry-run             仅提取信息，不实际下载")
        print("  --verbose             启用详细输出")
        print("  --max-magnets <数量>   最大处理的磁力链接数 (默认: 3)")
        print("  --max-matches <数量>   最大处理的匹配项数 (默认: 3)")
        print("示例:")
        print("  python3 main_downloader.py https://www.dygangs.net/ys/ 捕风追影")
        print("  python3 main_downloader.py https://www.dygangs.net/dsj/ 年少有为 --type tv --max-magnets 10")
        print("  python3 main_downloader.py https://www.dygangs.net/ys/ 速度与激情 --dry-run --verbose")
        return
    
    # 解析命令行参数
    url = sys.argv[1]
    keyword = sys.argv[2]
    
    output = None
    content_type = "movie"
    dry_run = False
    verbose = False
    max_magnets = 3
    max_matches = 3
    
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            content_type = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--dry-run":
            dry_run = True
            i += 1
        elif sys.argv[i] == "--verbose":
            verbose = True
            i += 1
        elif sys.argv[i] == "--max-magnets" and i + 1 < len(sys.argv):
            try:
                max_magnets = int(sys.argv[i + 1])
            except ValueError:
                print("错误: --max-magnets 必须是数字")
                return
            i += 2
        elif sys.argv[i] == "--max-matches" and i + 1 < len(sys.argv):
            try:
                max_matches = int(sys.argv[i + 1])
            except ValueError:
                print("错误: --max-matches 必须是数字")
                return
            i += 2
        else:
            print(f"未知参数: {sys.argv[i]}")
            return
    
    # 创建主下载程序实例
    main_downloader = MainDownloader()
    
    # 运行完整流程
    main_downloader.run(
        url=url,
        keyword=keyword,
        output=output,
        content_type=content_type,
        dry_run=dry_run,
        verbose=verbose,
        max_magnets=max_magnets,
        max_matches=max_matches
    )


if __name__ == "__main__":
    main()
