// Write test memory to Vertex AI Memory Bank
const memory = require('./memory_client.js');

async function main() {
  const testMemory = {
    source: 'local',
    user: 'mitchell',
    content: 'Phase 0 test memory - Vertex AI Memory Bank implementation',
    tags: ['phase0']
  };
  
  try {
    const result = await memory.write(testMemory);
    console.log('Memory written successfully:', JSON.stringify(result, null, 2));
    if (result.response && result.response.generatedMemories) {
      console.log('Generated memories:', result.response.generatedMemories.length);
    }
    process.exit(0);
  } catch (error) {
    console.error('Error writing memory:', error.message);
    process.exit(1);
  }
}

main();
