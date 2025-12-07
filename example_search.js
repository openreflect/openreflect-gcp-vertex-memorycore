// Search and retrieve memories from Vertex AI Memory Bank
const memory = require('./memory_client.js');

async function main() {
  const scope = { user_id: 'mitchell' };
  
  try {
    const results = await memory.search(scope);
    console.log('Found memories:', results.length);
    results.forEach((r, i) => {
      const mem = r.memory || r;
      console.log(`Memory ${i + 1}:`, mem.fact || mem.content || JSON.stringify(mem));
    });
    if (results.length > 0) {
      console.log('Round-trip successful!');
      process.exit(0);
    } else {
      console.log('No memories found');
      process.exit(1);
    }
  } catch (error) {
    console.error('Error searching memories:', error.message);
    process.exit(1);
  }
}

main();
