# fh6-automation

Forza Horizon 6 自動化工具。透過模板比對偵測遊戲畫面，自動按鍵完成重複操作。

[Demo 影片](https://youtu.be/eOvWOZAUlZo) • [下載最新版](https://github.com/nelsonlaidev/fh6-automation/releases/latest/download/FH6Automation_Setup.exe)

## 功能

| 步驟                   | 說明                             |
| ---------------------- | -------------------------------- |
| 刷技能點 (farm_sp)     | 自動重複跑活動累積技能點         |
| 購買車輛 (buy_car)     | 在汽車展售中心大量購入同一輛車   |
| 升級車輛 (upgrade_car) | 逐輛進入車輛熟練度並解鎖超級轉盤 |
| 移除車輛 (remove_car)  | 從車庫批量刪除車輛               |

## 安裝注意事項

首次執行時，Windows SmartScreen 可能會顯示「Windows 已保護您的電腦」警告，點擊「其他資訊」→「仍要執行」即可正常執行。

這個警告完全無害，顯示的原因是程式沒有經過程式碼簽章。本專案是開源軟體，程式碼簽章憑證每年需要 $200 美元以上，因此目前沒有簽章。

## 使用方式

加入 Discord 伺服器獲取最新消息與支援：[https://discord.gg/ncK4mhPkwt](https://discord.gg/ncK4mhPkwt)

## 開發

需要 Python 3.12 與 [uv](https://docs.astral.sh/uv/)。GUI 使用 PySide6（Qt6）。

### 從原始碼執行

```powershell
uv sync
uv run .\src\main.py
```

### 建置 .exe

```powershell
.\build_exe.ps1
```

## 支持

如果這個工具對你有幫助，歡迎請我喝杯咖啡 ☕

[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-support-ea4aaa?logo=githubsponsors)](https://github.com/sponsors/nelsonlaidev)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow?logo=buymeacoffee)](https://buymeacoffee.com/nelsonlaidev)

## 免責聲明

本工具僅供個人學習與研究用途。使用本工具可能違反遊戲服務條款，因使用本工具而導致的任何後果（包括但不限於帳號封禁）由使用者自行承擔。作者不承擔任何責任。

## 授權

[AGPL-3.0](LICENSE)
