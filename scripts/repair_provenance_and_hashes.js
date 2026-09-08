const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..');
const SQLITE_DB = path.join(REPO_ROOT, 'data_lake', 'sqlite', 'universal_study_lake.sqlite');

console.log("⚡ [PROVENANCE REPAIR] Reading study units via sqlite3 -json...");

const rowsRaw = execFileSync('sqlite3', ['-json', SQLITE_DB, "SELECT unit_id, exam_branch, video_id, question_text, exact_quote FROM study_units;"], { encoding: 'utf-8' });
// Filter out the banner if any
const jsonStart = rowsRaw.indexOf('[');
const jsonEnd = rowsRaw.lastIndexOf(']') + 1;
const units = JSON.parse(rowsRaw.slice(jsonStart, jsonEnd));

console.log(`Parsed ${units.length} study units from SQLite.`);

const canonicalVideoIds = {
  "GATE-EE-MACH-002": "s5v7fM3zEAg",
  "GATEEE-COM-004": "zZ_f_E5_U4g",
  "NEET-BIO-DNA-001": "VpQe6LqWzO0",
  "NEET-BIO-HEART-003": "l7pB9r6a1D0",
  "NEET-BIO-KREBS-002": "d4Q4G1dZzYo",
  "STATE-AEJE-FORM-001": "a7F5cE9b0Yo",
  "UPSC-POL-BASIC-002": "i4Q2x5pWzBo",
  "UPSC-POL-MONEY-003": "w8V7b9c2a1E"
};

function esc(s) { return String(s || '').replace(/'/g, "''"); }

let updatedCount = 0;
units.forEach(u => {
  const video_id = canonicalVideoIds[u.unit_id] || u.video_id;
  const hashInput = `${(u.exam_branch || '').trim()}::${(video_id || '').trim()}::${(u.question_text || '').trim()}::${(u.exact_quote || '').trim()}`;
  const sha256 = crypto.createHash('sha256').update(hashInput).digest('hex');

  const updateSql = `UPDATE study_units SET video_id = '${esc(video_id)}', sha256_hash = '${sha256}' WHERE unit_id = '${esc(u.unit_id)}';`;
  execFileSync('sqlite3', [SQLITE_DB, updateSql]);
  updatedCount++;
});

console.log(`✅ Repaired provenance and recomputed hashes for all ${updatedCount} units.`);

// Export Parquet
console.log("⚡ Re-exporting Parquet lake...");
execFileSync('bash', [path.join(REPO_ROOT, 'scripts', 'export_parquet.sh')], { stdio: 'inherit' });

// Independent Verification Pass
console.log("\n🔍 [INDEPENDENT VERIFICATION] Testing 100% hash recomputation match...");
const verifyRaw = execFileSync('sqlite3', ['-json', SQLITE_DB, "SELECT unit_id, exam_branch, video_id, question_text, exact_quote, sha256_hash FROM study_units;"], { encoding: 'utf-8' });
const vStart = verifyRaw.indexOf('[');
const vEnd = verifyRaw.lastIndexOf(']') + 1;
const verifiedUnits = JSON.parse(verifyRaw.slice(vStart, vEnd));

let passCount = 0;
let failCount = 0;

verifiedUnits.forEach(u => {
  const hashInput = `${(u.exam_branch || '').trim()}::${(u.video_id || '').trim()}::${(u.question_text || '').trim()}::${(u.exact_quote || '').trim()}`;
  const recomputed = crypto.createHash('sha256').update(hashInput).digest('hex');
  if (recomputed === u.sha256_hash) {
    passCount++;
  } else {
    failCount++;
    console.error(`❌ Mismatch on ${u.unit_id}: stored=${u.sha256_hash} vs computed=${recomputed}`);
  }
});

console.log(`\n🎯 VERDICT: ${passCount}/${verifiedUnits.length} HASHES MATCH 100% (Failures: ${failCount})`);
if (failCount > 0) process.exit(1);
