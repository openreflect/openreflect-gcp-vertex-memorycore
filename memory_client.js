const { GoogleAuth } = require('google-auth-library');
const https = require('https');
const PROJECT_ID = 'directed-asset-479716-f6';
const LOCATION = 'us-central1';
const BASE_URL = `https://${LOCATION}-aiplatform.googleapis.com/v1beta1`;
let authClient = null, agentEngineName = null;

async function getAccessToken() {
  if (!authClient) authClient = new GoogleAuth({ scopes: ['https://www.googleapis.com/auth/cloud-platform'] });
  return (await (await authClient.getClient()).getAccessToken()).token;
}

async function ensureAgentEngine() {
  if (agentEngineName) return agentEngineName;
  const token = await getAccessToken();
  const op = await makeRequest(`${BASE_URL}/projects/${PROJECT_ID}/locations/${LOCATION}/reasoningEngines`, 'POST', {}, token);
  if (op.name && op.name.includes('/operations/')) {
    while (true) {
      await new Promise(r => setTimeout(r, 1000));
      const status = await makeRequest(`${BASE_URL}/${op.name}`, 'GET', null, token);
      if (status.done && status.response) { agentEngineName = status.response.name; break; }
    }
  } else agentEngineName = op.name;
  if (!agentEngineName) throw new Error('Failed to create agent engine');
  return agentEngineName;
}

function makeRequest(url, method, body, token) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = https.request({ hostname: u.hostname, path: u.pathname + u.search, method: method, headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 400) reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        else { try { resolve(JSON.parse(data)); } catch (e) { reject(new Error(`Parse error: ${data}`)); } }
      });
    });
    req.on('error', reject);
    if (body && Object.keys(body).length > 0) req.write(JSON.stringify(body));
    req.end();
  });
}

async function write(memoryData) {
  const engineName = await ensureAgentEngine();
  const op = await makeRequest(`${BASE_URL}/${engineName}/memories:generate`, 'POST', {
    direct_memories_source: { direct_memories: [{ fact: `${memoryData.content} [source: ${memoryData.source}, user: ${memoryData.user}, tags: ${memoryData.tags.join(',')}]` }] },
    scope: { user_id: memoryData.user }
  }, await getAccessToken());
  if (op.name && op.name.includes('/operations/')) {
    while (true) {
      await new Promise(r => setTimeout(r, 1000));
      const status = await makeRequest(`${BASE_URL}/${op.name}`, 'GET', null, await getAccessToken());
      if (status.done) return status;
    }
  }
  return op;
}

async function search(scope, query) {
  const engineName = await ensureAgentEngine();
  const result = await makeRequest(`${BASE_URL}/${engineName}/memories:retrieve`, 'POST', { scope }, await getAccessToken());
  return result.retrievedMemories || [];
}

async function retrieve(scope) {
  return await search(scope);
}

module.exports = { write, search, retrieve };
