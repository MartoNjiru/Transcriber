const { timingSafeEqual } = require("node:crypto");

const MAX_TRANSCRIPT_LENGTH = 40_000;

function sendJson(res, status, value) {
  res.status(status).setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(value));
}

function equalSecret(candidate, expected) {
  if (typeof candidate !== "string" || !expected) return false;
  const candidateBuffer = Buffer.from(candidate);
  const expectedBuffer = Buffer.from(expected);
  return (
    candidateBuffer.length === expectedBuffer.length &&
    timingSafeEqual(candidateBuffer, expectedBuffer)
  );
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return sendJson(res, 405, { error: "Method not allowed." });
  }

  const accessCode = process.env.APP_ACCESS_CODE;
  const apiKey = process.env.OPENAI_API_KEY;
  if (!accessCode || !apiKey) {
    return sendJson(res, 503, {
      error: "The server is not configured. Ask the site owner to check its settings.",
    });
  }

  const body = req.body;
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return sendJson(res, 400, { error: "Request body must be a JSON object." });
  }
  if (!equalSecret(body.accessCode, accessCode)) {
    return sendJson(res, 401, { error: "The app access code is incorrect." });
  }

  const { action, transcript } = body;
  if (action !== "suggest" && action !== "summarize") {
    return sendJson(res, 400, { error: "Choose a supported assistant action." });
  }
  if (typeof transcript !== "string" || !transcript.trim()) {
    return sendJson(res, 400, { error: "Add transcript text before requesting AI output." });
  }
  if (transcript.length > MAX_TRANSCRIPT_LENGTH) {
    return sendJson(res, 413, { error: "The transcript is too long for one request." });
  }

  const baseUrl = (process.env.OPENAI_BASE_URL || "https://api.openai.com/v1").replace(/\/+$/, "");
  let endpoint;
  try {
    const parsedBaseUrl = new URL(baseUrl);
    if (parsedBaseUrl.protocol !== "https:" && parsedBaseUrl.protocol !== "http:") {
      throw new Error("Unsupported URL scheme.");
    }
    endpoint = new URL(`${parsedBaseUrl.toString().replace(/\/+$/, "")}/chat/completions`);
  } catch {
    return sendJson(res, 500, { error: "The configured AI provider URL is invalid." });
  }

  const systemPrompt = action === "suggest"
    ? "You are a meeting companion. Suggest a concise, truthful response based only on the transcript. Clearly label assumptions and do not invent facts. Keep the suggestion easy to review before the user speaks."
    : "Summarize the provided meeting transcript. Separate key points, decisions, open questions, and action items. Do not invent details.";
  const userPrompt = action === "suggest"
    ? `Suggest a helpful response to the latest discussion:\n\n${transcript.trim()}`
    : `Summarize this meeting:\n\n${transcript.trim()}`;
  const model = process.env.OPENAI_CHAT_MODEL || "gpt-4o-mini";
  const maxTokens = Number.parseInt(process.env.OPENAI_MAX_COMPLETION_TOKENS || "1200", 10);

  if (!Number.isInteger(maxTokens) || maxTokens < 1 || maxTokens > 8192) {
    return sendJson(res, 500, {
      error: "The configured maximum completion token count is invalid.",
    });
  }

  let providerResponse;
  try {
    providerResponse = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        max_tokens: maxTokens,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
      }),
      signal: AbortSignal.timeout(25_000),
    });
  } catch {
    return sendJson(res, 502, { error: "Could not reach the configured AI provider." });
  }

  if (!providerResponse.ok) {
    return sendJson(res, 502, {
      error: `The AI provider returned HTTP ${providerResponse.status}. Check its model and API settings.`,
    });
  }

  let providerData;
  try {
    providerData = await providerResponse.json();
  } catch {
    return sendJson(res, 502, { error: "The AI provider returned an invalid response." });
  }
  const content = providerData?.choices?.[0]?.message?.content;
  if (typeof content !== "string" || !content.trim()) {
    return sendJson(res, 502, { error: "The AI provider returned no text." });
  }

  return sendJson(res, 200, { text: content.trim() });
};
