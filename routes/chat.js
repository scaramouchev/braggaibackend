import express from 'express';
import { requireAuth } from '../middleware/auth.js';

const router = express.Router();

const PYTHON_URL = process.env.PYTHON_URL;
const PYTHON_INTERNAL_KEY = process.env.PYTHON_INTERNAL_KEY;

router.post('/', requireAuth, async (req, res) => {
  try {
    const { question } = req.body;
    if (typeof question !== 'string' || !question.trim() || question.length > 1000) {
      return res.status(400).json({ error: 'Invalid question' });
    }

    const response = await fetch(`${PYTHON_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Key': PYTHON_INTERNAL_KEY,
      },
      body: JSON.stringify({
        question: req.body.question,
      }),
    });

    const data = await response.json();

    res.status(response.status).json(data);
  } catch (error) {
    console.error('Python chat error:', error);
    res.status(500).json({ error: 'Chat service unavailable' });
  }
});

export default router;