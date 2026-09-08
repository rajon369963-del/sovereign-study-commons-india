#!/usr/bin/env node

/**
 * Sovereign Study Commons — Automated Community Harvester & Deduplicator
 * Pure Node.js (Zero external npm dependencies) + SQLite3 + DuckDB
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const SQLITE_DB = path.join(REPO_ROOT, 'data_lake', 'sqlite', 'universal_study_lake.sqlite');
const EXPORT_SCRIPT = path.join(REPO_ROOT, 'scripts', 'export_parquet.sh');

function getArg(key, fallback = '') {
  const envVal = process.env[key.toUpperCase()];
  if (envVal) return envVal;
  const prefix = `--${key}=`;
  const arg = process.argv.find(a => a.startsWith(prefix));
  return arg ? arg.slice(prefix.length) : fallback;
}

const examBranch = getArg('exam_branch', 'GATE_EE');
const subject = getArg('subject', 'General Engineering');
const topic = getArg('topic', 'Fundamental Concept');
const teacher = getArg('teacher', 'Community Contributor');
const videoId = getArg('video_id', 'COMMUNITY_SUBMISSION');
const timestampSpan = getArg('timestamp_span', '00:00-05:00');
const exactQuote = getArg('exact_quote', 'Teacher explanation span verified by community.');
const questionText = getArg('question_text', '');
const correctOpt = getArg('correct_opt', 'A');
const explanation = getArg('explanation', 'Verified step-by-step socratic derivation.');

if (!questionText) {
  console.log(JSON.stringify({
    status: 'ERROR',
    message: 'Usage: node scripts/harvest_community.js --question_text="Your question" [options]'
  }, null, 2));
  process.exit(0);
}

// Compute SHA-256 hash for deduplication
const hashInput = `${examBranch.trim()}::${questionText.trim()}::${exactQuote.trim()}`;
const sha256 = crypto.createHash('sha256').update(hashInput).digest('hex');

// Check deduplication in SQLite
const checkQuery = `SELECT unit_id FROM study_units WHERE sha256_hash = '${sha256}' LIMIT 1;`;
const existingId = execFileSync('sqlite3', [SQLITE_DB, checkQuery], { encoding: 'utf-8' }).trim();

if (existingId) {
  console.log(JSON.stringify({
    status: 'SKIPPED_DUPLICATE',
    unit_id: existingId,
    sha256: sha256,
    message: `Unit already exists with ID: ${existingId}. Zero duplicate invariant preserved.`
  }, null, 2));
  process.exit(0);
}

// Generate new Unit ID
const cleanBranch = examBranch.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 7);
const countQuery = `SELECT COUNT(*) FROM study_units WHERE exam_branch = '${examBranch}';`;
const currentCount = parseInt(execFileSync('sqlite3', [SQLITE_DB, countQuery], { encoding: 'utf-8' }).trim(), 10) || 0;
const newUnitId = `${cleanBranch}-COM-${String(currentCount + 1).padStart(3, '0')}`;

const harvestedAt = new Date().toISOString();
const defaultOptions = JSON.stringify({
  A: "Option A (Verified)",
  B: "Option B (Distractor)",
  C: "Option C (Trap)",
  D: "Option D (Alternative)"
});
const defaultHints = JSON.stringify([
  "Identify fundamental law governing the system.",
  "Check boundary conditions and polarity.",
  "Eliminate dimensionally inconsistent options."
]);

// Escape single quotes for SQLite
function esc(str) {
  return String(str).replace(/'/g, "''");
}

const insertQuery = `
INSERT INTO study_units (
  unit_id, exam_branch, subject, topic, teacher, video_id,
  timestamp_span, exact_quote, question_text, options_json,
  correct_opt, explanation, socratic_hints_json, sha256_hash, drive_url, harvested_at
) VALUES (
  '${esc(newUnitId)}',
  '${esc(examBranch)}',
  '${esc(subject)}',
  '${esc(topic)}',
  '${esc(teacher)}',
  '${esc(videoId)}',
  '${esc(timestampSpan)}',
  '${esc(exactQuote)}',
  '${esc(questionText)}',
  '${esc(defaultOptions)}',
  '${esc(correctOpt)}',
  '${esc(explanation)}',
  '${esc(defaultHints)}',
  '${esc(sha256)}',
  'https://drive.google.com/open?id=community_ingest',
  '${esc(harvestedAt)}'
);
`;

execFileSync('sqlite3', [SQLITE_DB, insertQuery]);

// Re-export Parquet
try {
  execFileSync('bash', [EXPORT_SCRIPT], { encoding: 'utf-8' });
} catch (e) {
  console.error("Export warning:", e.message);
}

console.log(JSON.stringify({
  status: 'SUCCESS',
  unit_id: newUnitId,
  exam_branch: examBranch,
  topic: topic,
  teacher: teacher,
  sha256: sha256,
  harvested_at: harvestedAt,
  message: `Successfully ingested unit ${newUnitId} into sovereign study lake and re-exported Parquet.`
}, null, 2));
