const APP_ID = process.env.DISCORD_APP_ID;
const BOT_TOKEN = process.env.DISCORD_BOT_TOKEN;

if (!APP_ID || !BOT_TOKEN) {
  console.error("Set DISCORD_APP_ID and DISCORD_BOT_TOKEN environment variables");
  process.exit(1);
}

const commands = [
  {
    name: "AIに聞く",
    type: 3, // MESSAGE command (right-click context menu)
  },
  {
    name: "ask",
    description: "AIに質問する（記事についての深掘りやアイデア出し）",
    type: 1, // CHAT_INPUT (slash command)
    options: [
      {
        name: "question",
        description: "質問内容",
        type: 3, // STRING
        required: true,
      },
    ],
  },
];

const url = `https://discord.com/api/v10/applications/${APP_ID}/commands`;

const response = await fetch(url, {
  method: "PUT",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bot ${BOT_TOKEN}`,
  },
  body: JSON.stringify(commands),
});

if (response.ok) {
  console.log("Commands registered successfully!");
  console.log(await response.json());
} else {
  console.error("Failed to register commands:", response.status);
  console.error(await response.text());
}
