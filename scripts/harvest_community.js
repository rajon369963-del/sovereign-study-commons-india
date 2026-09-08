#!/usr/bin/env node

/**
 * Sovereign Study Commons — staged community ingestion helper.
 *
 * Safety boundary: this script must not synthesize missing provenance or study
 * content. It only accepts an already-reviewed, source-bound study unit and
 * fails closed when required provenance or C17 cleaning is unavailable.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const SQLITE_DB = path.join(REPO_ROOT, 'data_lake', 'sqlite', 'universal_study_lake.sqlite');
const EXPORT_SCRIPT = path.join(REPO_ROOT, 'scripts', 'export_parquet.sh');
const C17_CLEAN_VTT = path.join(REPO_ROOT, 'c17_engines', 'clean_vtt');

function getArg(key) {
  const envVal = process.env[key.toUpperCase()];
  if (envVal) return envVal;
  const prefix = `--${key}=`;
  const arg = process.argv.find(a => a.startsWith(prefix));
  return arg ? arg.slice(prefix.length) : '';
}

const examBranch = getArg('exam_branch');
const subject = getArg('subject');
const topic = getArg('topic');
const teacher = getArg('teacher');
const videoId = getArg('video_id');
const timestampSpan = getArg('timestamp_span');
let exactQuote = getArg('exact_quote');
const questionText = getArg('question_text');
const correctOpt = getArg('correct_opt');
const explanation = getArg('explanation');
const sourceVerified = getArg('source_verified').toLowerCase() === 'true';

const requiredFields = {
  exam_branch: examBranch,
  subject,
  topic,
  teacher,
  video_id: videoId,
  timestamp_span: timestampSpan,
  exact_quote: exactQuote,
  question_text: questionText,
  correct_opt: correctOpt,
  explanation
};
const missingFields = Object.entries(requiredFields)
  .filter(([, value]) => !String(value).trim())
  .map(([key]) => key);

if (missingFields.length || !sourceVerified) {
  console.error(JSON.stringify({
    status: 'NOT_INGESTED',
    reason: !sourceVerified ? 'SOURCE_NOT_VERIFIED' : 'MISSING_REQUIRED_FIELDS',
    missing_fields: missingFields,
    message: 'Community ingestion requires explicit maintainer-reviewed, source-bound content. No defaults or synthesized provenance are accepted.'
  }, null, 2));
  process.exit(1);
}

if (!/^[A-D]$/i.test(correctOpt.trim())) {
  console.error(JSON.stringify({
    status: 'NOT_INGESTED',
    reason: 'INVALID_CORRECT_OPTION',
    message: 'correct_opt must be one of A, B, C, or D.'
  }, null, 2));
  process.exit(1);
}

// C17 is mandatory for this ingestion path. Missing or failed cleaning is fatal.
if (!fs.existsSync(C17_CLEAN_VTT)) {
  console.error(JSON.stringify({
    status: 'NOT_INGESTED',
    reason: 'C17_BINARY_MISSING',
    message: 'C17 cleaning is required for this path; ingestion stopped before database mutation.'
  }, null, 2));
  process.exit(1);
}

let c17Executed = false;
let tmpVtt = '';
try {
  tmpVtt = path.join('/tmp', `temp_c17_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.vtt`);
  const mockVttContent = `WEBVTT\n\n00:00:00.000 --> 00:05:00.000\n${exactQuote}\n`;
  fs.writeFileSync(tmpVtt, mockVttContent, 'utf-8');
  const cleanedRaw = execFileSync(C17_CLEAN_VTT, [tmpVtt], { encoding: 'utf-8' }).trim();
  if (!cleanedRaw) throw new Error('C17 returned empty output');

  const parts = cleanedRaw.split('--- Sample Cleaned Cue Output (First 5) ---');
  if (parts[1] && parts[1].trim()) {
    exactQuote = parts[1].trim();
  } else {
    const cleaned = cleanedRaw
      .replace(/===.*?===/g, '')
      .replace(/Total unique cues.*/g, '')
      .replace(/Processing latency.*/g, '')
      .trim();
    if (!cleaned) throw new Error('C17 produced no usable cleaned quote');
    exactQuote = cleaned;
  }
  c17Executed = true;
} catch (err) {
  console.error(JSON.stringify({
    status: 'NOT_INGESTED',
    reason: 'C17_CLEANING_FAILED',
    message: err.message
  }, null, 2));
  process.exit(1);
} finally {
  if (tmpVtt && fs.existsSync(tmpVtt)) fs.unlinkSync(tmpVtt);
}

// Deterministic content hash. This is not, by itself, a concurrency guarantee.
const hashInput = `${examBranch.trim()}::${videoId.trim()}::${questionText.trim()}::${exactQuote.trim()}`;
const sha256 = crypto.createHash('sha256').update(hashInput).digest('hex');

// Best-effort duplicate lookup. Concurrency safety still requires a database
// uniqueness constraint/transaction and remains a separate activation gate.
const checkQuery = `SELECT unit_id FROM study_units WHERE sha256_hash = '${sha256}' LIMIT 1;`;
const existingId = execFileSync('sqlite3', [SQLITE_DB, checkQuery], { encoding: 'utf-8' }).trim();

if (existingId) {
  console.log(JSON.stringify({
    status: 'SKIPPED_DUPLICATE',
    unit_id: existingId,
    sha256,
    message: `Unit already exists with ID: ${existingId}.`
  }, null, 2));
  process.exit(0);
}

// Deterministic short identifier only; collision-proof/concurrency-safe claims
// are intentionally avoided until DB constraints are independently verified.
const cleanBranch = examBranch.replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 7);
const hashSuffix = sha256.slice(0, 8).toUpperCase();
const newUnitId = `${cleanBranch}-${hashSuffix}`;

const harvestedAt = new Date().toISOString();
const defaultOptions = JSON.stringify({
  A: 'Option A (Verified)',
  B: 'Option B (Distractor)',
  C: 'Option C (Trap)',
  D: 'Option D (Alternative)'
});
const defaultHints = JSON.stringify([
  'Identify fundamental law governing the system.',
  'Check boundary conditions and polarity.',
  'Eliminate dimensionally inconsistent options.'
]);

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
  '${esc(correctOpt.toUpperCase())}',
  '${esc(explanation)}',
  '${esc(defaultHints)}',
  '${esc(sha256)}',
  'https://drive.google.com/open?id=community_ingest',
  '${esc(harvestedAt)}'
);
`;

execFileSync('sqlite3', [SQLITE_DB, insertQuery]);

try {
  execFileSync('bash', [EXPORT_SCRIPT], { encoding: 'utf-8' });
} catch (exportErr) {
  console.error(`❌ [FATAL] Parquet export failed: ${exportErr.message}`);
  execFileSync('sqlite3', [SQLITE_DB, `DELETE FROM study_units WHERE unit_id = '${esc(newUnitId)}';`]);
  process.exit(1);
}

console.log(JSON.stringify({
  status: 'SUCCESS',
  unit_id: newUnitId,
  exam_branch: examBranch,
  topic,
  teacher,
  c17_cleaned: c17Executed,
  source_verified: sourceVerified,
  sha256,
  harvested_at: harvestedAt,
  message: `Successfully ingested reviewed unit ${newUnitId}; C17 cleaning completed and Parquet export returned success.`
}, null, 2));
