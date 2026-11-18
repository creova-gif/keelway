// Vercel serverless function fallback: POST /api/early-access
// Kept in sync with website/src/app/api/early-access/route.ts

const REPO_OWNER = 'creova-gif';
const REPO_NAME = 'keelway';
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
  const role = typeof body?.role === 'string' ? body.role.trim() : 'unspecified';
  const region = typeof body?.region === 'string' ? body.region.trim() : 'global';

  if (!EMAIL_RE.test(email)) {
    return json(res, 400, { ok: false, error: 'a valid work email is required' });
  }

  const token = process.env.EARLY_ACCESS_GH_TOKEN;
  if (!token) {
    console.error('early-access: EARLY_ACCESS_GH_TOKEN is not set');
    return json(res, 500, { ok: false, error: 'signup intake is not configured yet' });
  }

  const interestLabels = {
    hybrid_routing: 'Hybrid OpenCore + Frontier API Routing',
    local: 'Local desktop IDE & OpenCore Weights',
    agent: 'Approval-Gated Autonomous Agents',
    team: 'Team Governance & Spend Caps',
    vpc: 'Dedicated Customer-Owned VPC Fleet',
  };

  const roleLabels = {
    ai_engineer: 'AI / Platform Engineer',
    cto_vp: 'CTO / VP of Engineering',
    security_lead: 'Security & Governance Architect',
    ml_researcher: 'Applied ML / OpenCore Researcher',
  };

  const issueBody = [
    `**Email:** ${email}`,
    `**Role:** ${roleLabels[role] || role}`,
    `**Primary workload:** ${interestLabels[interest] || interest}`,
    `**Deployment region:** ${region.toUpperCase()}`,
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
          title: `Early access: ${email} (${region.toUpperCase()})`,
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
