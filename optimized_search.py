#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的本地 HTML 搜索工具

根据关键词在本地 HTML 文件中搜索相关链接，并提取磁力链接
"""

import urllib.parse
import sys
import os
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional


def search_local_html(
    file_path: str, 
    keywords: List[str], 
    search_types: List[str] = None, 
    case_sensitive: bool = False,
    fuzzy_match: bool = True,
    max_results: int = 50
) -> List[Dict]:
    """
    在本地 HTML 文件中搜索相关链接
    
    Args:
        file_path: HTML 文件路径
        keywords: 搜索关键词列表
        search_types: 搜索类型，可选值: ['links', 'magnets', 'images']
        case_sensitive: 是否区分大小写
        fuzzy_match: 是否使用模糊匹配
        max_results: 最大结果数
        
    Returns:
        搜索结果列表
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    if not os.path.isfile(file_path):
        raise IsADirectoryError(f"不是文件: {file_path}")
    
    # 默认搜索类型
    if search_types is None:
        search_types = ['links']
    
    # 读取文件
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        try:
            with open(file_path, 'r', encoding='gb2312', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            raise Exception(f"读取文件失败: {e}")
    
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    
    # 搜索链接
    if 'links' in search_types:
        links_results = _search_links(soup, keywords, case_sensitive, fuzzy_match, max_results)
        results.extend(links_results)
    
    # 搜索磁力链接
    if 'magnets' in search_types:
        magnets_results = _search_magnets(soup, content, keywords, case_sensitive, fuzzy_match, max_results)
        results.extend(magnets_results)
    
    # 搜索图片
    if 'images' in search_types:
        images_results = _search_images(soup, keywords, case_sensitive, fuzzy_match, max_results)
        results.extend(images_results)
    
    # 排序结果（按匹配度和相关性）
    results = _sort_results(results, keywords)
    
    # 限制结果数量
    return results[:max_results]


def _search_links(
    soup: BeautifulSoup, 
    keywords: List[str], 
    case_sensitive: bool, 
    fuzzy_match: bool, 
    max_results: int
) -> List[Dict]:
    """
    搜索链接
    """
    results = []
    seen = set()
    
    # 扩展搜索范围，包括更多类型的链接
    link_selectors = [
        'a.c2',  # 原始选择器
        'a[href]',  # 所有链接
        'a.title',  # 标题链接
        'a[class*="link"]',  # 包含 link 的类
        'a[class*="title"]',  # 包含 title 的类
    ]
    
    for selector in link_selectors:
        for a in soup.select(selector):
            href = a.get('href')
            if not href:
                continue
            
            # 去重
            if href in seen:
                continue
            seen.add(href)
            
            text = a.get_text(strip=True)
            full_url = href if href.startswith('http') else urllib.parse.urljoin('https://www.dygangs.net', href)
            
            # 检查是否匹配关键词
            match_score = _calculate_match_score(
                text, href, keywords, case_sensitive, fuzzy_match
            )
            
            if match_score > 0:
                results.append({
                    'type': 'link',
                    'url': full_url,
                    'text': text,
                    'match_score': match_score,
                    'selector': selector,
                    'position': len(results)
                })
            
            if len(results) >= max_results:
                break
        
        if len(results) >= max_results:
            break
    
    return results


def _search_magnets(
    soup: BeautifulSoup, 
    content: str, 
    keywords: List[str], 
    case_sensitive: bool, 
    fuzzy_match: bool, 
    max_results: int
) -> List[Dict]:
    """
    搜索磁力链接
    """
    results = []
    seen = set()
    
    # 从链接中提取磁力链接
    for a in soup.find_all('a', href=re.compile(r'^magnet:')):
        href = a['href'].strip()
        if href in seen:
            continue
        seen.add(href)
        
        text = a.get_text(strip=True) or a.get('title') or ""
        
        # 检查是否匹配关键词
        match_score = _calculate_match_score(
            text, href, keywords, case_sensitive, fuzzy_match
        )
        
        if match_score > 0:
            results.append({
                'type': 'magnet',
                'url': href,
                'text': text,
                'match_score': match_score,
                'position': len(results)
            })
        
        if len(results) >= max_results:
            break
    
    # 从文本中提取磁力链接
    magnet_pattern = re.compile(r'(magnet:\?xt=[^"\'\s<>]+)')
    for m in magnet_pattern.findall(content):
        if m in seen:
            continue
        seen.add(m)
        
        # 尝试从上下文提取文件名
        idx = content.find(m)
        context = content[max(0, idx-200): idx+200]
        fn = re.search(r'([\u4e00-\u9fff\w \-_.()]{3,80})', context)
        text = fn.group(1).strip() if fn else ""
        
        # 检查是否匹配关键词
        match_score = _calculate_match_score(
            text, m, keywords, case_sensitive, fuzzy_match
        )
        
        if match_score > 0:
            results.append({
                'type': 'magnet',
                'url': m,
                'text': text,
                'match_score': match_score,
                'position': len(results)
            })
        
        if len(results) >= max_results:
            break
    
    return results


def _search_images(
    soup: BeautifulSoup, 
    keywords: List[str], 
    case_sensitive: bool, 
    fuzzy_match: bool, 
    max_results: int
) -> List[Dict]:
    """
    搜索图片
    """
    results = []
    seen = set()
    
    for img in soup.find_all('img', src=True):
        src = img['src'].strip()
        if not src:
            continue
        
        # 去重
        if src in seen:
            continue
        seen.add(src)
        
        alt = img.get('alt', '').strip()
        title = img.get('title', '').strip()
        text = alt or title
        
        full_url = src if src.startswith('http') else urllib.parse.urljoin('https://www.dygangs.net', src)
        
        # 检查是否匹配关键词
        match_score = _calculate_match_score(
            text, src, keywords, case_sensitive, fuzzy_match
        )
        
        if match_score > 0:
            results.append({
                'type': 'image',
                'url': full_url,
                'text': text,
                'match_score': match_score,
                'position': len(results)
            })
        
        if len(results) >= max_results:
            break
    
    return results


def _calculate_match_score(
    text: str, 
    url: str, 
    keywords: List[str], 
    case_sensitive: bool, 
    fuzzy_match: bool
) -> int:
    """
    计算匹配得分
    """
    score = 0
    
    if not case_sensitive:
        text = text.lower()
        url = url.lower()
        keywords = [kw.lower() for kw in keywords]
    
    for keyword in keywords:
        # 文本匹配
        if keyword in text:
            score += 3  # 文本匹配权重更高
        elif fuzzy_match and _fuzzy_match(keyword, text):
            score += 2
        
        # URL 匹配
        if keyword in url:
            score += 2
        elif fuzzy_match and _fuzzy_match(keyword, url):
            score += 1
    
    return score


def _fuzzy_match(pattern: str, text: str) -> bool:
    """
    模糊匹配
    """
    if not pattern or not text:
        return False
    
    # 简单的模糊匹配：检查关键词的主要部分是否在文本中
    pattern_parts = re.findall(r'[\u4e00-\u9fff\w]+', pattern)
    if not pattern_parts:
        return pattern in text
    
    # 至少匹配一个主要部分
    for part in pattern_parts:
        if len(part) > 1 and part in text:
            return True
    
    return False


def _sort_results(results: List[Dict], keywords: List[str]) -> List[Dict]:
    """
    排序结果
    """
    # 按匹配得分降序排序
    results.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    return results


def extract_magnets_from_url(url: str) -> List[Dict]:
    """
    从 URL 提取磁力链接
    """
    try:
        # 添加项目根目录到 Python 路径
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from dygangs_auto_downloader import DygangsAutoDownloader
        
        downloader = DygangsAutoDownloader()
        downloader.dry_run = True
        
        magnets = downloader.extract_magnets_from_page(url)
        return magnets
    except Exception as e:
        print(f"提取磁力链接失败: {e}")
        return []


def main():
    """
    主函数
    """
    if len(sys.argv) < 3:
        print("使用方法:")
        print("  python optimized_search.py <html_file> <关键词1> [<关键词2> ...]")
        print("  python optimized_search.py <html_file> <关键词> --type <类型>")
        print("  python optimized_search.py <html_file> <关键词> --case-sensitive")
        print("  python optimized_search.py <html_file> <关键词> --exact-match")
        print("示例:")
        print("  python optimized_search.py www.dygangs.net_index.html 电影")
        print("  python optimized_search.py www.dygangs.net_index.html 阿凡达 电影")
        print("  python optimized_search.py www.dygangs.net_index.html 电影 --type links")
        print("  python optimized_search.py www.dygangs.net_index.html 电影 --type links,magnets")
        return
    
    file_path = sys.argv[1]
    
    # 解析参数
    keywords = []
    search_types = ['links', 'magnets']
    case_sensitive = False
    fuzzy_match = True
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            search_types = sys.argv[i + 1].split(',')
            i += 2
        elif sys.argv[i] == "--case-sensitive":
            case_sensitive = True
            i += 1
        elif sys.argv[i] == "--exact-match":
            fuzzy_match = False
            i += 1
        else:
            keywords.append(sys.argv[i])
            i += 1
    
    if not keywords:
        print("错误: 请提供搜索关键词")
        return
    
    try:
        print(f"正在搜索文件: {file_path}")
        print(f"搜索关键词: {', '.join(keywords)}")
        print(f"搜索类型: {', '.join(search_types)}")
        print(f"区分大小写: {case_sensitive}")
        print(f"模糊匹配: {fuzzy_match}")
        print()
        
        # 执行搜索
        results = search_local_html(
            file_path, 
            keywords, 
            search_types, 
            case_sensitive, 
            fuzzy_match
        )
        
        # 打印搜索结果
        print(f"找到 {len(results)} 个匹配结果:")
        print("-" * 80)
        
        for i, result in enumerate(results[:20], 1):  # 只显示前20个
            print(f"{i}. [{result['type']}] 匹配得分: {result['match_score']}")
            print(f"   URL: {result['url']}")
            if result['text']:
                print(f"   文本: {result['text']}")
            print(f"   选择器: {result.get('selector', 'N/A')}")
            print("-" * 80)
        
        if len(results) > 20:
            print(f"... 还有 {len(results) - 20} 个结果未显示")
        
        # 对前几个结果提取磁力链接
        if results and 'links' in search_types:
            print("\n提取磁力链接:")
            print("-" * 80)
            
            link_results = [r for r in results if r['type'] == 'link'][:3]  # 只处理前3个
            
            for i, result in enumerate(link_results, 1):
                print(f"{i}. 处理链接: {result['url']}")
                print(f"   文本: {result['text']}")
                
                magnets = extract_magnets_from_url(result['url'])
                if magnets:
                    print(f"   提取到 {len(magnets)} 个磁力链接:")
                    for j, magnet in enumerate(magnets[:2], 1):  # 只显示前2个
                        print(f"     {j}. {magnet['filename']}")
                        print(f"        {magnet['magnet'][:100]}...")
                    if len(magnets) > 2:
                        print(f"     ... 还有 {len(magnets) - 2} 个磁力链接")
                else:
                    print(f"   未找到磁力链接")
                print("-" * 80)
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
