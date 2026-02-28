#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成下载工具

完整工作流程：
1. 保存远程网页到本地
2. 在本地文件中搜索电影/电视剧
3. 提取磁力链接并自动下载
"""

import urllib.parse
import sys
import os
import tempfile
from typing import List, Dict, Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dygangs_auto_downloader import DygangsAutoDownloader
from optimized_search import search_local_html, extract_magnets_from_url


class IntegratedDownloader:
    """
    集成下载器类
    """
    
    def __init__(self):
        """
        初始化集成下载器
        """
        self.downloader = DygangsAutoDownloader()
        self.temp_dir = tempfile.gettempdir()
    
    def download_content(
        self, 
        keywords: List[str],
        save_url: str = "https://www.dygangs.net",
        content_type: str = "auto",
        max_results: int = 10,
        dry_run: bool = False
    ) -> bool:
        """
        完整下载流程
        
        Args:
            keywords: 搜索关键词列表
            save_url: 要保存的网页 URL
            content_type: 内容类型，可选值: "auto", "movie", "tv"
            max_results: 最大结果数
            dry_run: 是否为干运行模式
            
        Returns:
            操作是否成功
        """
        print(f"=== 集成下载工具 ===")
        print(f"搜索关键词: {', '.join(keywords)}")
        print(f"目标网站: {save_url}")
        print(f"内容类型: {content_type}")
        print(f"干运行模式: {dry_run}")
        print()
        
        # 步骤 1: 保存远程网页到本地
        print("步骤 1: 保存远程网页到本地")
        local_file = self._save_remote_page(save_url)
        if not local_file:
            print("❌ 保存网页失败")
            return False
        print(f"✅ 网页已保存到: {local_file}")
        print()
        
        # 步骤 2: 在本地文件中搜索
        print("步骤 2: 在本地文件中搜索相关内容")
        search_results = self._search_local_content(local_file, keywords, max_results)
        if not search_results:
            print("❌ 未找到相关内容")
            return False
        print(f"✅ 找到 {len(search_results)} 个相关结果")
        print()
        
        # 步骤 3: 提取磁力链接并下载
        print("步骤 3: 提取磁力链接并下载")
        download_success = self._extract_and_download(
            search_results, 
            content_type, 
            dry_run
        )
        
        print()
        if download_success:
            print("🎉 下载任务已成功添加到 Transmission")
        else:
            print("⚠️  部分或全部下载任务添加失败")
        
        return download_success
    
    def _save_remote_page(self, url: str) -> Optional[str]:
        """
        保存远程网页到本地
        
        Args:
            url: 远程网页 URL
            
        Returns:
            本地文件路径
        """
        try:
            # 生成唯一的临时文件名
            filename = f"dygangs_{int(time.time())}.html"
            local_path = os.path.join(self.temp_dir, filename)
            
            # 使用 DygangsAutoDownloader 的 save_page 方法
            saved_path = self.downloader.save_page(url, local_path)
            
            if saved_path and os.path.exists(saved_path):
                return saved_path
            else:
                return None
        except Exception as e:
            print(f"保存网页时出错: {e}")
            return None
    
    def _search_local_content(
        self, 
        file_path: str, 
        keywords: List[str], 
        max_results: int
    ) -> List[Dict]:
        """
        在本地文件中搜索相关内容
        
        Args:
            file_path: 本地文件路径
            keywords: 搜索关键词列表
            max_results: 最大结果数
            
        Returns:
            搜索结果列表
        """
        try:
            results = search_local_html(
                file_path=file_path,
                keywords=keywords,
                search_types=['links'],
                case_sensitive=False,
                fuzzy_match=True,
                max_results=max_results
            )
            return results
        except Exception as e:
            print(f"搜索本地内容时出错: {e}")
            return []
    
    def _extract_and_download(
        self, 
        search_results: List[Dict], 
        content_type: str, 
        dry_run: bool
    ) -> bool:
        """
        提取磁力链接并下载
        
        Args:
            search_results: 搜索结果列表
            content_type: 内容类型
            dry_run: 是否为干运行模式
            
        Returns:
            操作是否成功
        """
        if dry_run:
            self.downloader.dry_run = True
        
        success_count = 0
        total_count = 0
        
        # 处理前几个最相关的结果
        for i, result in enumerate(search_results[:5]):  # 只处理前5个结果
            print(f"\n处理结果 {i+1}/{len(search_results[:5])}:")
            print(f"标题: {result.get('text', '无标题')}")
            print(f"链接: {result.get('url', '无链接')}")
            print(f"匹配得分: {result.get('match_score', 0)}")
            
            url = result.get('url')
            if not url:
                print("❌ 无效的链接")
                continue
            
            # 提取磁力链接
            magnets = extract_magnets_from_url(url)
            if not magnets:
                print("❌ 未找到磁力链接")
                continue
            
            print(f"找到 {len(magnets)} 个磁力链接")
            
            # 确定下载目录
            download_dir = self._get_download_dir(content_type, url)
            
            # 添加到 Transmission
            for j, magnet in enumerate(magnets[:3]):  # 只添加前3个磁力链接
                total_count += 1
                magnet_uri = magnet.get('magnet')
                filename = magnet.get('filename', '未知文件')
                
                print(f"  添加磁力链接 {j+1}/{len(magnets[:3])}: {filename}")
                
                success = self.downloader.add_to_transmission(
                    magnet_uri, 
                    download_dir, 
                    filename
                )
                
                if success:
                    success_count += 1
                    print(f"    ✅ 成功添加到 Transmission")
                else:
                    print(f"    ❌ 添加失败")
        
        return success_count > 0
    
    def _get_download_dir(self, content_type: str, url: str) -> str:
        """
        确定下载目录
        
        Args:
            content_type: 内容类型
            url: 内容 URL
            
        Returns:
            下载目录路径
        """
        if content_type == "movie":
            return "/vol1/1000/downloads/movies"
        elif content_type == "tv":
            return "/vol1/1000/downloads/tv"
        else:
            # 自动判断
            if '/dsj/' in url:
                return "/vol1/1000/downloads/tv"
            else:
                return "/vol1/1000/downloads/movies"


import time

def main():
    """
    主函数
    """
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 integrated_downloader.py <关键词1> [<关键词2> ...] [选项]")
        print("选项:")
        print("  --url <网址>           指定要爬取的网站 URL (默认: https://www.dygangs.net)")
        print("  --type <类型>          指定内容类型: movie, tv, auto (默认: auto)")
        print("  --max-results <数量>   指定最大搜索结果数 (默认: 10)")
        print("  --dry-run              干运行模式，不实际添加下载任务")
        print("示例:")
        print("  python3 integrated_downloader.py 阿凡达")
        print("  python3 integrated_downloader.py 权力的游戏 --type tv")
        print("  python3 integrated_downloader.py 速度与激情 --max-results 5")
        print("  python3 integrated_downloader.py 阿凡达 --dry-run")
        return
    
    # 解析参数
    keywords = []
    save_url = "https://www.dygangs.net"
    content_type = "auto"
    max_results = 10
    dry_run = False
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--url" and i + 1 < len(sys.argv):
            save_url = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--type" and i + 1 < len(sys.argv):
            content_type = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--max-results" and i + 1 < len(sys.argv):
            max_results = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--dry-run":
            dry_run = True
            i += 1
        else:
            keywords.append(sys.argv[i])
            i += 1
    
    if not keywords:
        print("错误: 请提供搜索关键词")
        return
    
    # 创建集成下载器并执行下载
    downloader = IntegratedDownloader()
    success = downloader.download_content(
        keywords=keywords,
        save_url=save_url,
        content_type=content_type,
        max_results=max_results,
        dry_run=dry_run
    )
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
