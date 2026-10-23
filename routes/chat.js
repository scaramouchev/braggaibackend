import express from 'express';
import { pipeline } from '@xenova/transformers';
import { createClient } from '@supabase/supabase-js';
import Groq from 'groq-sdk';
import { requireAuth } from '../middleware/auth.js';

const router = express.Router();

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);
const groq = new Groq({ apiKey: process.env.GROQ_KEY });

let embedder;
async function getEmbedder() {
  if (!embedder) {
    embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
  }
  return embedder;
}

router.post('/', requireAuth, async (req, res) => {
  try {
    const { message } = req.body;
    if (!message) return res.status(400).json({ error: 'message required' });

    const model = await getEmbedder();
    const output = await model(message, { pooling: 'mean', normalize: true });
    const embedding = Array.from(output.data);

    const { data: matches, error } = await supabase.rpc('match_documents', {
      query_embedding: embedding,
      match_count: 5,
    });
    if (error) return res.status(500).json({ error: error.message });

    const context = (matches || []).map((m) => m.content).join('\n\n');

    const completion = await groq.chat.completions.create({
      model: 'openai/gpt-oss-20b',
      messages: [
        { role: 'system', content: `Use ONLY this FAMU info:\n${context}` },
        { role: 'user', content: message },
      ],
    });

    res.json({ reply: completion.choices[0].message.content });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

export default router;
