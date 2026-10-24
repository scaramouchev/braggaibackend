// routes/auth.js
import express from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import db from '../db.js';
import { requireAuth } from '../middleware/auth.js';

const router = express.Router();

const JWT_SECRET = process.env.JWT_SECRET;
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '7d';
const COOKIE_NAME = 'braggai_token';
const isProd = process.env.NODE_ENV === 'production';

const cookieOptions = {
  httpOnly: true,
  secure: true,
  sameSite: 'none',
  maxAge: 7 * 24 * 60 * 60 * 1000,
  path: '/',
};

function signToken(user) {
  return jwt.sign(
    { sub: user.id, email: user.email, role: user.role },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );
}

function publicUser(user) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
  };
}

router.post('/signup', async (req, res) => {
  const { name, email, password } = req.body || {};

  if (!name || !email || !password) {
    return res.status(400).json({ error: 'Name, email, and password are required.' });
  }

  if (String(password).length < 8) {
    return res.status(400).json({ error: 'Password must be at least 8 characters.' });
  }

  const normalizedEmail = String(email).trim().toLowerCase();

  const { data: existing, error: existingError } = await db
    .from('users')
    .select('id')
    .eq('email', normalizedEmail)
    .maybeSingle();

  if (existingError) {
    return res.status(500).json({ error: 'Database error.' });
  }
  if (existing) {
    return res.status(409).json({ error: 'That email is already registered.' });
  }

  const password_hash = await bcrypt.hash(String(password), 12);

  const { data: user, error: insertError } = await db
    .from('users')
    .insert([{ name: String(name).trim(), email: normalizedEmail, password_hash }])
    .select('id, name, email, role')
    .single();

  if (insertError) {
    return res.status(500).json({ error: 'Could not create user.' });
  }

  const token = signToken(user);
  res.cookie(COOKIE_NAME, token, cookieOptions);
  res.status(201).json({ user: publicUser(user) });
});

router.post('/login', async (req, res) => {
  const { email, password } = req.body || {};

  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required.' });
  }

  const normalizedEmail = String(email).trim().toLowerCase();
  const { data: user, error } = await db
    .from('users')
    .select('*')
    .eq('email', normalizedEmail)
    .maybeSingle();

  if (error || !user) {
    return res.status(401).json({ error: 'Email or password is incorrect.' });
  }

  const ok = await bcrypt.compare(String(password), user.password_hash);
  if (!ok) {
    return res.status(401).json({ error: 'Email or password is incorrect.' });
  }

  const token = signToken(user);
  res.cookie(COOKIE_NAME, token, cookieOptions);
  res.json({ user: publicUser(user) });
});

router.post('/logout', (req, res) => {
  res.clearCookie(COOKIE_NAME, {
    httpOnly: true,
    secure: true,
    sameSite: 'none',
    path: '/',
  });
  res.json({ ok: true });
});

router.get('/me', requireAuth, async (req, res) => {
  const { data: user, error } = await db
    .from('users')
    .select('id, name, email, role')
    .eq('id', req.user.sub)
    .maybeSingle();

  if (error || !user) {
    return res.status(401).json({ error: 'Not authenticated' });
  }

  res.json({ user: publicUser(user) });
});

export default router;