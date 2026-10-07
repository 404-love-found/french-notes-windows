FrenchNotes 0.1.0 — Windows 本地法语笔记

适用系统：Windows 10 / 11，64 位（x64）。运行时不需要安装 Python。
应用界面为中文。CSV 和 Word 文档保存在你自己的电脑上。

启动
1. 安装版：运行 FrenchNotes-Setup-0.1.0.exe，按照向导安装。
   安装仅针对当前用户，默认无需管理员权限。
   可从开始菜单或桌面快捷方式打开 FrenchNotes。
2. 免安装版：解压 FrenchNotes-0.1.0-Windows-x64.zip 后，双击 FrenchNotes.exe。
   也可以单独使用 FrenchNotes.exe。

录入和导出
1. 每行输入一个法语单词或句子。
2. 点击“分析与去重”，检查自动分类；必要时手动修改为单词或句子。
3. 点击“录入新内容”，仅将当前 CSV 和本批输入中不存在的内容写入 CSV。
4. 点击“导出全部为 Word”，将全部已保存内容分类导出为本地 .docx 文件。
   可使用 Microsoft Word 或其他兼容 .docx 的软件打开导出文件。

重复比较规则
忽略首尾空格、连续空格和大小写差异；保留法语重音和标点差异。
自动分类使用本地规则；多词词组等内容可以手动调整分类。

数据位置
默认：%LOCALAPPDATA%\FrenchNotes\notes.csv
设置：%LOCALAPPDATA%\FrenchNotes\settings.json
软件内可选择其他本地 CSV 文件；免安装版也使用上述默认数据目录。
Word 文档保存到导出时选择的位置。
升级或卸载软件会保留笔记数据；删除软件前请自行备份重要 CSV 和 Word 文件。

文件校验
SHA256SUMS.txt 记录对应发布文件的 SHA-256 值。
可在 PowerShell 中运行 Get-FileHash .\FrenchNotes.exe -Algorithm SHA256 进行比对。
本版本的程序和安装包尚未数字签名，Windows 可能显示未知发布者提示。

项目与更新
https://github.com/404-love-found/french-notes-windows
https://github.com/404-love-found/french-notes-windows/releases
