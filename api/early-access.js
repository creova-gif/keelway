// Vercel serverless function: POST /api/early-access
// Files each early-access request as a GitHub issue on this repo.
// Requires an EARLY_ACCESS_GH_TOKEN env var (fine-grained PAT, Issues: write
// only, scoped to creova-gif/kora) set in the Vercel project settings.

const REPO_OWNER = 'creova-gif';
const REPO_NAME = 'kora';
const LABEL = 'early-access';
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function json(res, status, body) {
  res.status(status).setHeader('content-type', 'application/json');
  res.end(JSON.stringify(body));
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    return json(res, 405, { ok: false, error: 'method not allowed' });
  }

  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch { body = {}; }
  }
  const email = typeof body?.email === 'string' ? body.email.trim() : '';
  const interest = typeof body?.interest === 'string' ? body.interest.trim() : 'unspecified';

  if (!EMAIL_RE.test(email)) {
    return json(res, 400, { ok: false, error: 'a valid work email is required' });
  }

  const token = process.env.EARLY_ACCESS_GH_TOKEN;
  if (!token) {
    console.error('early-access: EARLY_ACCESS_GH_TOKEN is not set');
    return json(res, 500, { ok: false, error: 'signup intake is not configured yet' });
  }

  const interestLabels = {
    local: 'Local desktop IDE (Studio)',
    agent: 'Building reusable agents',
    team: 'Team workspaces',
    vpc: 'Running in my own VPC',
  };

  const issueBody = [
    `**Email:** ${email}`,
    `**Primary interest:** ${interestLabels[interest] || interest}`,
    `**Submitted:** ${new Date().toISOString()}`,
    '',
    '_Filed automatically from the Request Early Access form on the marketing site._',
  ].join('\n');

  try {
    const ghRes = await fetch(
      `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/issues`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'User-Agent': 'keelway-early-access-intake',
        },
        body: JSON.stringify({
          title: `Early access: ${email}`,
          body: issueBody,
          labels: [LABEL],
        }),
      }
    );

    if (!ghRes.ok) {
      const detail = await ghRes.text();
      console.error('early-access: GitHub API error', ghRes.status, detail);
      return json(res, 502, { ok: false, error: 'could not record the request, try again shortly' });
    }

    return json(res, 200, { ok: true });
  } catch (err) {
    console.error('early-access: request failed', err);
    return json(res, 502, { ok: false, error: 'could not record the request, try again shortly' });
  }
};
