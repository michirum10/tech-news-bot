import { verifyKey } from "discord-interactions";

const INTERACTION_TYPE = { PING: 1, APPLICATION_COMMAND: 2 };
const COMMAND_TYPE = { CHAT_INPUT: 1, MESSAGE: 3 };
const RESPONSE_TYPE = {
  PONG: 1,
  CHANNEL_MESSAGE: 4,
  DEFERRED: 5,
};

export default {
  async fetch(request, env, ctx) {
    if (request.method === "GET") {
      return new Response("arxiv-hn-bot is running");
    }

    const signature = request.headers.get("X-Signature-Ed25519");
    const timestamp = request.headers.get("X-Signature-Timestamp");
    const body = await request.text();

    const isValid = await verifyKey(
      body,
      signature,
      timestamp,
      env.DISCORD_PUBLIC_KEY
    );
    if (!isValid) {
      return new Response("Invalid signature", { status: 401 });
    }

    const interaction = JSON.parse(body);

    if (interaction.type === INTERACTION_TYPE.PING) {
      return jsonResponse({ type: RESPONSE_TYPE.PONG });
    }

    if (interaction.type === INTERACTION_TYPE.APPLICATION_COMMAND) {
      ctx.waitUntil(processCommand(interaction, env));
      return jsonResponse({ type: RESPONSE_TYPE.DEFERRED });
    }

    return jsonResponse({ type: RESPONSE_TYPE.CHANNEL_MESSAGE, data: { content: "Unknown interaction" } });
  },
};

async function processCommand(interaction, env) {
  try {
    const { content, context } = extractContent(interaction);
    const answer = await callGemini(content, context, env);
    await sendFollowup(interaction, env, answer);
  } catch (err) {
    console.error("processCommand error:", err);
    await sendFollowup(interaction, env, `エラーが発生しました: ${err.message}`);
  }
}

function extractContent(interaction) {
  const { data } = interaction;

  if (data.type === COMMAND_TYPE.MESSAGE) {
    const messages = data.resolved.messages;
    const msg = messages[Object.keys(messages)[0]];
    return {
      content: msg.content,
      context: "ユーザーがこのニュース記事について分析を求めています。",
    };
  }

  if (data.type === COMMAND_TYPE.CHAT_INPUT) {
    const question = data.options[0].value;
    return {
      content: question,
      context: "ユーザーがAI/テクノロジーに関する質問をしています。記事やニュースに基づいてアイデアや分析を提供してください。",
    };
  }

  return { content: "不明なコマンド", context: "" };
}

async function callGemini(content, context, env) {
  const prompt = `あなたはAI/LLM開発に詳しいテックアドバイザーです。

${context}

以下の内容を分析し、日本語で回答してください：
- 重要なポイントの解説
- 個人開発やプロジェクトへの活用アイデア
- 関連する技術や手法の提案

専門用語は英語のまま残してください。簡潔に、でも具体的に。

---
${content}`;

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key=${env.GEMINI_API_KEY}`;

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
    }),
  });

  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`Gemini API error ${resp.status}: ${errText}`);
  }

  const result = await resp.json();
  const text =
    result.candidates?.[0]?.content?.parts?.[0]?.text || "回答を生成できませんでした。";

  if (text.length > 2000) {
    return text.slice(0, 1997) + "...";
  }
  return text;
}

async function sendFollowup(interaction, env, content) {
  const url = `https://discord.com/api/v10/webhooks/${env.DISCORD_APP_ID}/${interaction.token}`;

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });

  if (!resp.ok) {
    console.error("Followup failed:", resp.status, await resp.text());
  }
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
