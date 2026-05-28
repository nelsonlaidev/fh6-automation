# Changelog

## Unreleased

- 修正：Windows 使用者名稱含非 ASCII 字元（如中文）時無法載入模板的問題
- **Breaking**：設定檔中 `[delete]` section 已重新命名為 `[remove_car]`。升級後舊設定會被忽略並使用預設值，下次儲存時會自動寫入新格式。如需保留原設定，請手動將 `config.ini` 中的 `[delete]` 改為 `[remove_car]`。

## v0.1.0

- 初始版本
- 功能：刷技能點、購買車輛、升級車輛、移除車輛
- GUI 設定頁面
- 啟動時檢查更新
