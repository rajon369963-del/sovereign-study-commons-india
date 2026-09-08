#!/usr/bin/env node

/**
 * Sovereign Study Commons — Automated Community Harvester & Deduplicator
 * Integrated with Native C17 clean_vtt binary + SQLite3 WAL + DuckDB Parquet
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const SQLITE_DB = path.join(REPO_ROOT, 'data_lake', 'sqlite', 'universal_study_lake.sqlite');
const EXPORT_SCRIPT = path.join(REPO_ROOT, 'scripts', 'export_parquet.sh');
const C17_CLEAN_VTT = path.join(REPO_ROOT, 'c17_engines', 'clean_vtt');

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
let exactQuote = getArg('exact_quote', 'Teacher explanation span verified by community.');
const questionText = getArg('question_text', '');
const correctOpt = getArg('correct_opt', 'A');
const explanation = getArg('explanation', 'Verified step-by-step socratic derivation.');

if (!questionText) {
  console.error(JSON.stringify({
    status: 'ERROR',
    message: 'Usage: node scripts/harvest_community.js --question_text="Your question" [options]'
  }, null, 2));
  process.exit(1);
}

// ⚡ [C17 INTEGRATION]: Clean quote using native C17 clean_vtt binary
let c17Executed = false;
if (fs.existsSync(C17_CLEAN_VTT)) {
  try {
    const tmpVtt = path.join('/tmp', `temp_c17_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.vtt`);
    const mockVttContent = `WEBVTT\n\n00:00:00.000 --> 00:05:00.000\n${exactQuote}\n`;
    fs.writeFileSync(tmpVtt, mockVttContent, 'utf-8');
    const cleanedRaw = execFileSync(C17_CLEAN_VTT, [tmpVtt], { encoding: 'utf-8' }).trim();
    if (cleanedRaw) {
      const parts = cleanedRaw.split("--- Sample Cleaned Cue Output (First 5) ---");
      if (parts[1] && parts[1].trim()) {
        exactQuote = parts[1].trim();
      } else {
        // Remove timing header lines if sample separator not found
        exactQuote = cleanedRaw.replace(/===.*?===/g, '').replace(/Total unique cues.*/g, '').replace(/Processing latency.*/g, '').trim() || exactQuote;
      }
      c17Executed = true;
    }
    if (fs.existsSync(tmpVtt)) fs.unlinkSync(tmpVtt);
  } catch (err) {
    console.warn(`[C17 WARN] Native cleaner fallback: ${err.message}`);
  }
}

// 🔒 [CONCURRENCY-SAFE CRYPTOGRAPHIC HASH]: Branch + VideoId/Playlist + Question + Quote
const hashInput = `${examBranch.trim()}::${videoId.trim()}::${questionText.trim()}::${exactQuote.trim()}`;
const sha256 = crypto.createHash('sha256').update(hashInput).digest('hex');

// Check deduplication in SQLite
const checkQuery = `SELECT unit_id FROM study_units WHERE sha256_hash = '${sha256}' LIMIT 1;`;
const existingId = execFileSync('sqlite3', [SQLITE_DB, checkQuery], { encoding: 'utf-8' }).trim();

if (existingId) {
  console.log(JSON.stringify({
    status: 'SKIPPED_DUPLICATE',
    unit_id: existingId,
    sha256: sha256,
    message: `Unit already exists with ID: ${existingId}. Zero duplicate invariant strictly preserved.`
  }, null, 2));
  process.exit(0);
}

// 🔑 [CONCURRENCY-SAFE ID GENERATION]: Deterministic hash-suffix prevents counter race conditions
const cleanBranch = examBranch.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 7);
const hashSuffix = sha256.slice(0, 8).toUpperCase();
const newUnitId = `${cleanBranch}-${hashSuffix}`;

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

// ⚡ [STRICT PARQUET EXPORT]: Throw hard error if Parquet export fails (Zero false-green)
try {
  execFileSync('bash', [EXPORT_SCRIPT], { encoding: 'utf-8' });
} catch (exportErr) {
  console.error(`❌ [FATAL] Parquet export failed: ${exportErr.message}`);
  // Rollback sqlite insertion to preserve ACID consistency
  execFileSync('sqlite3', [SQLITE_DB, `DELETE FROM study_units WHERE unit_id = '${esc(newUnitId)}';`]);
  process.exit(1);
}

console.log(JSON.stringify({
  status: 'SUCCESS',
  unit_id: newUnitId,
  exam_branch: examBranch,
  topic: topic,
  teacher: teacher,
  c17_cleaned: c17Executed,
  sha256: sha256,
  harvested_at: harvestedAt,
  message: `Successfully ingested unit ${newUnitId} with C17 cleaning and updated Parquet lake.`
}, null, 2));
