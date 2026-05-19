# GitHub Pages 发布步骤

## 一、准备

需要：

1. 一个 GitHub 账号。
2. 本地电脑安装 Git（推荐）。
3. 本包完整文件夹。

仓库建议名称：

```text
philippines-coconut-weather-dashboard
```

建议先用 Public 仓库，因为你希望发给别人看。

## 二、在 GitHub 新建仓库

1. 登录 GitHub。
2. 点击右上角 `+` → `New repository`。
3. Repository name 填：

```text
philippines-coconut-weather-dashboard
```

4. 选择 `Public`。
5. 不要勾选 README（本包已经有 README）。
6. 点击 `Create repository`。

## 三、把本地包上传到 GitHub

进入本地包目录：

```powershell
cd "D:\张雅\油脂分析\月桂酸油\菲律宾天气\philippines_coconut_weather_dashboard_publish_v1"
```

首次上传：

```powershell
git init
git add .
git commit -m "Initial Philippines coconut weather dashboard"
git branch -M main
git remote add origin https://github.com/你的用户名/philippines-coconut-weather-dashboard.git
git push -u origin main
```

如果 GitHub 提示登录，按浏览器弹出的登录/授权流程完成即可。

## 四、打开 GitHub Pages

进入 GitHub 仓库页面：

```text
Settings → Pages → Build and deployment → Source → GitHub Actions
```

选择 GitHub Actions 后保存。

## 五、手动跑第一次更新

进入：

```text
Actions → Update Philippines Coconut Weather Dashboard → Run workflow
```

第一次会从 1981 年开始建立历史数据，可能比较慢。成功后会自动发布网页。

网页链接大概是：

```text
https://你的用户名.github.io/philippines-coconut-weather-dashboard/
```

## 六、以后如何更新

设置成功后，GitHub Actions 会每天自动运行：

```text
UTC 00:20 = 北京/马尼拉时间 08:20
```

你也可以随时手动更新：

```text
Actions → Update Philippines Coconut Weather Dashboard → Run workflow
```

## 七、如果你想本地更新后上传

本地运行：

```powershell
.\publish_local_update.bat
```

这个脚本会：

1. 重新生成 `site/data/latest.json`。
2. 提交 `data/history` 和 `site`。
3. push 到 GitHub。

## 八、公开性提醒

Public GitHub Pages 是公开网页。不要把内部交易建议、客户信息、报价、账号密码、API key 放入仓库或网页。
