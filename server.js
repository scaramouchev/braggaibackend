// server.js
import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import cookieParser from 'cookie-parser';
import rateLimit from 'express-rate-limit';
import authRoutes from './routes/auth.js';
import chatRoutes from './routes/chat.js';

const app = express();
const PORT = process.env.PORT || 4000;

app.set('trust proxy', 1);

app.use(express.json({ limit: '1mb' }));
app.use(cookieParser());

app.use(cors({
  origin: process.env.CLIENT_ORIGIN || 'http://127.0.0.1:5500',
  credentials: true,
}));

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many attempts. Try again later.' },
});

const chatLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  message: { error: 'Slow down a bit.' },
});

app.use('/api/auth', authLimiter, authRoutes);

app.use('/api/chat', chatLimiter, chatRoutes);

app.get('/health', (req, res) => {
  res.json({ ok: true });
});

app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, () => {
  console.log(`BRAGGAI auth backend running on :${PORT}`);
});