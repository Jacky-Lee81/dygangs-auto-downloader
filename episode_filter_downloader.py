#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电视剧集数过滤下载器

功能：
1. 搜索电视剧
2. 根据指定集数过滤结果
3. 下载对应集数的磁力链接
"""

import urllib.parse
import sys
import os
import re
import time
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dygangs_auto_downloader import DygangsAutoDownloader


class EpisodeFilterDownloader:
    """
    电视剧集数过滤下载器
    """
    
    def __init__(self):
        """
        初始化集数过滤下载器
        """
        self.downloader = DygangsAutoDownloader()
        self.verbose = False
    
    def parse_episode_range(self, episode_str: str) -> List[int]:
        """
        解析集数范围字符串，如 "1-3" 或 "1,2,3" 或 "5"
        
        Args:
            episode_str: 集数范围字符串
            
        Returns:
            集数列表
        """
        episodes = []
        
        # 处理范围格式，如 "1-3"
        range_match = re.match(r'(\d+)-(\d+)', episode_str)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            episodes.extend(range(start, end + 1))
        # 处理逗号分隔格式，如 "1,2,3"
        elif ',' in episode_str:
            episodes.extend([int(x.strip()) for x in episode_str.split(',')])
        # 处理单个数字，如 "5"
        else:
            try:
                episodes.append(int(episode_str))
            except ValueError:
                print(f"警告: 无法解析集数 '{episode_str}'")
        
        return sorted(list(set(episodes)))  # 去重并排序
    
    def filter_episodes(self, magnets: List[Dict[str, str]], episodes: List[int]) -> List[Dict[str, str]]:
        """
        根据指定集数过滤磁力链接
        
        Args:
            magnets: 磁力链接列表
            episodes: 要下载的集数列表
            
        Returns:
            过滤后的磁力链接列表
        """
        filtered_magnets = []
        
        for magnet in magnets:
            filename = magnet.get('filename', '').lower()
            
            # 检查是否包含指定的集数
            for episode in episodes:
                # 匹配 "第X集" 格式
                if re.search(rf'第\s*{episode}\s*集', filename):
                    filtered_magnets.append(magnet)
                    break
                # 匹配 "X集" 格式
                elif re.search(rf'{episode}\s*集', filename):
                    filtered_magnets.append(magnet)
                    break
                # 匹配 "E[X]" 或 "EP[X]" 格式
                elif re.search(rf'[eE][pP]?\s*0*{episode}\b', filename):
                    filtered_magnets.append(magnet)
                    break
                # 匹配 "[X]" 格式（单独的数字，且前后有分隔符）
                elif re.search(rf'(?:^|[^\d])0*{episode}(?:[^\d]|$)', filename):
                    filtered_magnets.append(magnet)
                    break
        
        # 如果没有找到特定集数，但有"全集"或包含所需集数范围的链接，则使用这些
        if not filtered_magnets:
            for magnet in magnets:
                filename = magnet.get('filename', '').lower()
                
                # 检查是否包含集数范围，如 "01-04" 或 "1-4"
                for episode in episodes:
                    # 检查是否包含这个集数（在范围内）
                    if re.search(rf'(\d+)-(\d+)', filename):
                        range_match = re.search(rf'(\d+)-(\d+)', filename)
                        if range_match:
                            range_start = int(range_match.group(1))
                            range_end = int(range_match.group(2))
                            # 如果指定的集数在范围内
                            if any(range_start <= ep <= range_end for ep in episodes):
                                if magnet not in filtered_magnets:  # 避免重复
                                    filtered_magnets.append(magnet)
        
        return filtered_magnets
    
    def sort_magnets_by_quality(self, magnets: List[Dict[str, str]]) -> List[Dict[str, str]]:
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
            filename = magnet.get('filename', '').lower()
            
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
            if '高码' in filename or 'high' in filename:
                score += 50
            if '120fps' in filename:
                score += 40
            if '60fps' in filename:
                score += 30
            
            # 按其他质量指标评分
            if '蓝光' in filename or 'bluray' in filename:
                score += 30
            if 'hdr' in filename:
                score += 20
            if '原盘' in filename or 'remux' in filename:
                score += 40
            
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
    
    def download_tv_episodes_by_url(
        self,
        url: str,
        title: str,
        episodes: List[int],
        content_type: str = "tv",
        dry_run: bool = False
    ) -> bool:
        """
        通过URL直接下载指定电视剧的特定集数
        
        Args:
            url: 电视剧页面URL
            title: 电视剧标题
            episodes: 要下载的集数列表
            content_type: 内容类型 (movie/tv)
            dry_run: 是否为dry-run模式
            
        Returns:
            是否下载成功
        """
        if self.verbose:
            print(f"处理电视剧: {title}")
            print(f"页面URL: {url}")
            print(f"要下载的集数: {episodes}")
            print(f"Dry-run模式: {dry_run}")
        
        # 设置dry-run模式
        original_dry_run = self.downloader.dry_run
        self.downloader.dry_run = dry_run
        
        try:
            print(f"正在提取页面内容: {url}")
            
            # 提取磁力链接
            magnets = self.downloader.extract_magnets_from_page(url)
            
            if not magnets:
                print(f"在页面中未找到磁力链接: {url}")
                return False
            
            print(f"找到 {len(magnets)} 个磁力链接")
            
            # 按质量排序
            magnets = self.sort_magnets_by_quality(magnets)
            
            # 过滤特定集数
            filtered_magnets = self.filter_episodes(magnets, episodes)
            
            if not filtered_magnets:
                print(f"未找到指定集数 ({episodes}) 的磁力链接")
                
                # 如果没找到特定集数，但有包含这些集数的合集，则使用合集
                all_episodes = self.filter_episodes(magnets, list(range(1, 100)))  # 假设最多99集
                if all_episodes:
                    print(f"找到了包含所需集数的合集链接")
                    filtered_magnets = all_episodes
                else:
                    print("也没有找到包含所需集数的合集链接")
                    return False
            else:
                print(f"找到 {len(filtered_magnets)} 个符合集数要求的磁力链接")
            
            # 确定下载目录
            if content_type == "movie":
                download_dir = "/vol1/1000/downloads/movies"
            else:
                download_dir = "/vol1/1000/downloads/tv"
            
            # 添加到Transmission
            success_count = 0
            for magnet_info in filtered_magnets:
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
    
    def download_tv_episodes(
        self, 
        keyword: str, 
        episodes: List[int], 
        content_type: str = "tv", 
        dry_run: bool = False, 
        max_magnets: int = 10
    ) -> bool:
        """
        下载指定电视剧的特定集数
        
        Args:
            keyword: 搜索关键词
            episodes: 要下载的集数列表
            content_type: 内容类型 (movie/tv)
            dry_run: 是否为dry-run模式
            max_magnets: 最大处理的磁力链接数
            
        Returns:
            是否下载成功
        """
        if self.verbose:
            print(f"搜索关键词: {keyword}")
            print(f"要下载的集数: {episodes}")
            print(f"Dry-run模式: {dry_run}")
        
        # 设置dry-run模式
        original_dry_run = self.downloader.dry_run
        self.downloader.dry_run = dry_run
        
        try:
            # 搜索内容
            print(f"正在搜索: {keyword}")
            search_results = self.downloader.search_content(keyword)
            
            if not search_results:
                print(f"未找到关于 '{keyword}' 的相关内容")
                
                # 尝试手动访问已知的电视剧页面URL
                known_urls = {
                    '被隐匿的真相': 'https://www.dygangs.net/dsj/20260207/59011.htm',
                    '夜色正浓': 'https://www.dygangs.net/dsj/20260207/58972.htm'
                }
                
                if keyword in known_urls:
                    print(f"尝试访问已知页面: {known_urls[keyword]}")
                    return self.download_tv_episodes_by_url(
                        url=known_urls[keyword],
                        title=keyword,
                        episodes=episodes,
                        content_type=content_type,
                        dry_run=dry_run
                    )
                
                return False
            
            print(f"找到 {len(search_results)} 个相关结果:")
            for i, result in enumerate(search_results):
                print(f"  {i+1}. {result['title']} ({result['type']}) - {result['url']}")
            
            # 处理每个搜索结果
            success_count = 0
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
                magnets = self.downloader.extract_magnets_from_page(result['url'])
                
                if not magnets:
                    print(f"  在页面中未找到磁力链接")
                    continue
                
                print(f"  找到 {len(magnets)} 个磁力链接")
                
                # 按质量排序
                magnets = self.sort_magnets_by_quality(magnets)
                
                # 过滤特定集数
                filtered_magnets = self.filter_episodes(magnets, episodes)
                
                if not filtered_magnets:
                    print(f"  未找到指定集数 ({episodes}) 的磁力链接")
                    
                    # 如果没找到特定集数，但有"全集"或包含所需集数的链接，则使用
                    for mag in magnets:
                        filename = mag.get('filename', '').lower()
                        # 检查是否包含集数范围
                        for episode in episodes:
                            if re.search(rf'(\d+)-(\d+)', filename):
                                range_match = re.search(rf'(\d+)-(\d+)', filename)
                                if range_match:
                                    range_start = int(range_match.group(1))
                                    range_end = int(range_match.group(2))
                                    # 如果指定的集数在范围内
                                    if any(range_start <= ep <= range_end for ep in episodes):
                                        if mag not in filtered_magnets:  # 避免重复
                                            filtered_magnets.append(mag)
                    
                    if not filtered_magnets:
                        # 如果仍然没有找到，尝试是否有包含"全集"、"合集"等关键词的链接
                        for mag in magnets:
                            filename = mag.get('filename', '').lower()
                            if '全集' in filename or '合集' in filename or 'complete' in filename.lower() or 'all' in filename.lower():
                                filtered_magnets.append(mag)
                
                if not filtered_magnets:
                    print(f"  仍然未找到合适的链接")
                    continue
                else:
                    print(f"  找到 {len(filtered_magnets)} 个符合要求的磁力链接")
                
                # 限制处理的磁力链接数量
                filtered_magnets = filtered_magnets[:max_magnets]
                
                # 添加到Transmission
                for magnet_info in filtered_magnets:
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
    
    def run(self, keyword_with_episodes: str, content_type: str = "tv", dry_run: bool = False, verbose: bool = False):
        """
        运行完整流程
        
        Args:
            keyword_with_episodes: 包含关键词和集数的字符串，如 "被隐匿的真相 1-3"
            content_type: 内容类型
            dry_run: 是否为dry-run模式
            verbose: 是否启用详细输出
        """
        self.verbose = verbose
        
        print("=== 电视剧集数过滤下载器 ===")
        print(f"输入: {keyword_with_episodes}")
        print(f"内容类型: {content_type}")
        print(f"Dry-run: {dry_run}")
        print(f"详细输出: {verbose}")
        print()
        
        # 解析关键词和集数
        # 支持格式: "被隐匿的真相 1-3", "被隐匿的真相 1,2,3", "被隐匿的真相 5"
        parts = keyword_with_episodes.strip().split()
        if len(parts) < 2:
            print("❌ 输入格式错误，请使用 '关键词 集数范围' 格式")
            print("例如: '被隐匿的真相 1-3' 或 '被隐匿的真相 1,2,3' 或 '被隐匿的真相 5'")
            return False
        
        # 提取关键词和集数部分
        keyword = " ".join(parts[:-1])  # 除了最后一个部分，其余都是关键词
        episode_part = parts[-1]  # 最后一个部分是集数
        
        # 解析集数
        episodes = self.parse_episode_range(episode_part)
        
        if not episodes:
            print(f"❌ 无法解析集数: {episode_part}")
            print("支持的格式: 1-3, 1,2,3, 5")
            return False
        
        print(f"关键词: {keyword}")
        print(f"集数: {episodes}")
        print()
        
        # 下载指定集数
        success = self.download_tv_episodes(
            keyword=keyword,
            episodes=episodes,
            content_type=content_type,
            dry_run=dry_run
        )
        
        if success:
            print("\n=== 下载完成 ===")
            print("✅ 成功下载指定集数")
        else:
            print("\n=== 下载失败 ===")
            print("❌ 未能成功下载指定集数")
        
        return success


def main():
    """
    主函数
    """
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 episode_filter_downloader.py '<关键词 集数范围>' [选项]")
        print("选项:")
        print("  --type <类型>          指定内容类型: movie, tv (默认: tv)")
        print("  --dry-run             仅提取信息，不实际下载")
        print("  --verbose             启用详细输出")
        print("示例:")
        print("  python3 episode_filter_downloader.py '被隐匿的真相 1-3'")
        print("  python3 episode_filter_downloader.py '权力的游戏 1,2,3' --type tv")
        print("  python3 episode_filter_downloader.py '被隐匿的真相 5' --dry-run --verbose")
        return
    
    # 解析命令行参数
    keyword_with_episodes = sys.argv[1]
    
    content_type = "tv"  # 默认为电视剧
    dry_run = False
    verbose = False
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            content_type = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--dry-run":
            dry_run = True
            i += 1
        elif sys.argv[i] == "--verbose":
            verbose = True
            i += 1
        else:
            print(f"未知参数: {sys.argv[i]}")
            return
    
    # 创建集数过滤下载器实例
    episode_downloader = EpisodeFilterDownloader()
    
    # 运行完整流程
    episode_downloader.run(
        keyword_with_episodes=keyword_with_episodes,
        content_type=content_type,
        dry_run=dry_run,
        verbose=verbose
    )


if __name__ == "__main__":
    main()