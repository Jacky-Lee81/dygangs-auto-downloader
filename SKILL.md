---
name: dygangs-auto-downloader
description: |
  自动从 dygangs.net 下载电影和电视剧到 Transmission 下载器。
  支持搜索、缓存、下载追踪等功能。
---

# DyGangs Auto Downloader

自动从 dygangs.net 下载电影和电视剧到 Transmission 下载器。

## Tools

### dygangs_auto_downloader

自动下载电影/电视剧到 Transmission

**Usage:**

```bash
# 搜索并下载电影
python3 main_downloader.py <url> <keyword> [options]

# 搜索并下载电视剧
python3 main_downloader.py <url> <keyword> --type tv

# Dry-run 测试
python3 main_downloader.py <url> <keyword> --dry-run --verbose
```

**Options:**

- `--type <类型>`: 指定内容类型: movie, tv (默认: movie)
- `--output <路径>`: 指定HTML文件保存路径
- `--dry-run`: 仅提取信息，不实际下载
- `--verbose`: 启用详细输出
- `--max-magnets <数量>`: 最大处理的磁力链接数 (默认: 20)
- `--max-matches <数量>`: 最大处理的匹配项数 (默认: 3)

## Features

- 🎬 智能搜索电影/电视剧
- 💾 SQLite 缓存机制
- 📊 下载状态追踪
- 🔄 定时更新缓存
- 📦 Transmission 集成
- 🎯 集数过滤（电视剧）
- 📈 数据统计

## Database

缓存位置: `skills/dygangs-auto-downloader/data/movies.db`

支持查询缓存统计、下载记录等。
