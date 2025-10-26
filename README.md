# telegram-downloader-bot

# Telegram Multi-Platform Video Downloader Bot

A versatile and easy-to-use Telegram bot that downloads videos from multiple platforms like YouTube, Facebook, Instagram, and TikTok. Built with Python, `python-telegram-bot`, and `yt-dlp`.

**بوت تيليجرام متعدد المنصات لتحميل الفيديوهات**

بوت تيليجرام مرن وسهل الاستخدام يقوم بتحميل الفيديوهات من منصات متعددة مثل يوتيوب، فيسبوك، انستغرام، وتيك توك. تم بناؤه باستخدام بايثون ومكتبتي `python-telegram-bot` و `yt-dlp`.

---

## ✨ Features

- **Multi-Platform Support**: Download videos from YouTube, TikTok, Instagram, and Facebook.
- **Bilingual Interface**: Supports both English and Arabic, with language selection for users.
- **Admin Dashboard**: A private `/stats` command for the admin to monitor usage, including total users and total downloads.
- **Daily Usage Limits**: Protects the bot from abuse by limiting users to a configurable number of downloads per day.
- **Admin Alerts**: Automatically notifies the admin about important milestones (e.g., user growth) and excessive usage patterns.
- **Log Channel**: Automatically forwards a copy of every successfully downloaded video to a private channel for archiving.
- **Optimized for Free Hosting**: Designed to be deployed on free-tier services like Railway, with webhook support for efficiency.
- **Error Handling**: Gracefully handles common errors like private videos, invalid links, and files that are too large for Telegram.

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather )
- A Railway account (or any other hosting provider)
- Your Telegram User ID (to set as Admin)
- A private Telegram channel ID for logging (optional)

### Installation & Deployment

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/YOUR_USERNAME/telegram-video-downloader.git
    cd telegram-video-downloader
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables:**
    Create a `.env` file or set the following environment variables on your hosting provider (e.g., Railway ):
    - `TELEGRAM_TOKEN`: Your bot token.
    - `ADMIN_ID`: Your personal Telegram user ID.
    - `LOG_CHANNEL_ID`: (Optional) The ID of the private channel for logs.
    - `RAILWAY_STATIC_URL`: The public URL provided by Railway for your deployment.
    - `PORT`: The port your application will listen on (e.g., `8443`).

4.  **Run the bot:**
    The bot is configured to run with a webhook, which is ideal for server environments. Railway will automatically use the `Procfile` to start the web server.

## 🛠️ Bot Structure

- **`bot.py`**: The main application file. It contains all the logic for handling commands, processing video links, managing user stats, and setting up the webhook.
- **`messages.json`**: Contains all user-facing text in both English and Arabic. This makes it easy to add new languages or modify existing text.
- **`stats.json`**: A file generated at runtime to store user statistics, including daily download counts.
- **`user_languages.json`**: Stores the language preference for each user.
- **`requirements.txt`**: A list of Python libraries required for the project.
- **`Procfile`**: A configuration file for deployment on platforms like Heroku or Railway.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/w70t/telegram-video-downloader/issues ).

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.
