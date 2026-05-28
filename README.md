# fh6-automation

Forza Horizon 6 自動化工具。透過模板比對偵測遊戲畫面，自動按鍵完成重複操作。

▶ [Demo 影片](https://youtu.be/eOvWOZAUlZo)

📥 [下載最新版](https://github.com/nelsonlaidev/fh6-automation/releases/latest/download/FH6Automation_Setup.exe)

## 功能

| 步驟                   | 說明                             |
| ---------------------- | -------------------------------- |
| 刷技能點 (farm_sp)     | 自動重複跑活動累積技能點         |
| 購買車輛 (buy_car)     | 在汽車展售中心大量購入同一輛車   |
| 升級車輛 (upgrade_car) | 逐輛進入車輛熟練度並解鎖超級轉盤 |
| 移除車輛 (delete)      | 從車庫批量刪除車輛               |

## 使用方式

加入 Discord 伺服器獲取最新消息與支援：[https://discord.gg/ZzPp249n3](https://discord.gg/ZzPp249n3)

### 完整流程（超級轉盤刷取）

按照以下順序執行全部四個步驟：

1. **刷技能點** — 累積足夠的技能點。
2. **購買車輛** — 大量購入 22B（或其他目標車）。
3. **升級車輛** — 逐輛解鎖超級轉盤。
4. **移除車輛** — 刪除已升級的車，清出車庫空間。

### 注意事項

- 執行中請勿切換視窗，工具偵測到遊戲不在前景時會暫停。
- 若畫面對不上預期（例如彈出其他對話框），工具會自動中止並顯示原因。
- 預設模板為 22B，若要換其他車，用 GUI 底部「模板」按鈕開啟覆寫資料夾，放入自訂截圖。

## 模板

內建模板放在 `src/templates/*.png`（預設為 22B 的截圖，以 4K 擷取，適用於各解析度）。

若要覆寫（例如換其他車），將自訂 PNG 放到：

```
%USERPROFILE%\Documents\fh6-automation\templates\
```

同名檔案會覆蓋內建模板。使用 GUI 底部的「模板」按鈕可直接開啟該資料夾。

### 模板清單

```
# 刷技能點
farm_sp_start.png                  # 「開始活動」按鈕
farm_sp_anna.png                   # 駕駛中 Anna 對話框（消失代表本輪結束）
farm_sp_restart.png                # 「重新開始」按鈕
farm_sp_confirm.png                # 「確認」對話框

# 購買車輛
buy_car_detail.png                 # 車輛詳細頁（預設 22B）
buy_car_confirm.png                # 確認購買對話框
buy_car_purchase.png               # 購買確認（顯示價格 / 票券）

# 升級車輛
upgrade_car_target.png             # 車輛網格中的目標車
upgrade_car_explode.png            # Forzavista (X 展開) 按鈕
upgrade_car_my_cars.png            # 選單中「我的車輛」選項
upgrade_car_mastery.png            # 車輛熟練度入口
upgrade_car_wheelspin_unlocked.png # 超級轉盤技能已解鎖
upgrade_car_sort.png               # 排序選單

# 移除車輛
remove_car_target.png              # 車輛網格中的目標車
remove_car_button.png              # 選單中的刪除按鈕
remove_car_confirm.png             # 確定刪除對話框
```

### 製作模板的小提醒

- 裁緊一點，只留各畫面最有辨識度的部分（例如綠色 banner 文字），
  避免抓到會變動的區域（車輛圖、價格）。
- 存成 24-bit PNG，不要透明通道。

## 設定

INI 檔位於 `%USERPROFILE%\Documents\fh6-automation\config.ini`，首次執行時自動建立預設值。

## 開發

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
