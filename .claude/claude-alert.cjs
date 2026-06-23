#!/usr/bin/env node
/*
 * claude-alert — play a chime + spoken notice when Claude finishes a response.
 *
 * Triggered by the Claude Code "Stop" hook (see .claude/settings.json).
 * Cross-platform: works on macOS, Linux, and Windows. Runs on Node, which is
 * always present because Claude Code itself runs on Node — no extra install.
 *
 * ── CHANGE THE MESSAGE / VOICE HERE ──────────────────────────────────────────
 * Edit the DEFAULTS below, or override per-machine with environment variables:
 *   CLAUDE_ALERT_MESSAGE  spoken text
 *   CLAUDE_ALERT_VOICE    voice name (macOS `say -v '?'`, Windows installed voice)
 *   CLAUDE_ALERT_CHIME    path to a sound file (macOS/Linux only)
 *   CLAUDE_ALERT_SILENT   set to "1" to mute
 * ─────────────────────────────────────────────────────────────────────────────
 */

'use strict';

const DEFAULTS = {
  // 👇 Change the spoken message here (env var CLAUDE_ALERT_MESSAGE overrides it)
  message: 'Response finished, ready to continue',
  // 👇 Leave empty for the system default voice, or set a voice name
  voice: '',
};

if (process.env.CLAUDE_ALERT_SILENT === '1') process.exit(0);

const { spawn } = require('child_process');

const MESSAGE = process.env.CLAUDE_ALERT_MESSAGE || DEFAULTS.message;
const VOICE = process.env.CLAUDE_ALERT_VOICE || DEFAULTS.voice;

// Run a list of candidate commands, stopping at the first one that succeeds.
// A command that is missing (spawn error) or exits non-zero falls through to
// the next candidate. Calls done() when one succeeds or the list is exhausted.
function tryFirst(candidates, done) {
  const attempt = () => {
    const c = candidates.shift();
    if (!c) return done();
    let child;
    try {
      child = spawn(c.cmd, c.args, { stdio: 'ignore', windowsHide: true });
    } catch (_) {
      return attempt();
    }
    child.on('error', attempt);
    child.on('close', (code) => (code === 0 ? done() : attempt()));
  };
  attempt();
}

// Single-quote escape for PowerShell string literals.
const psQuote = (s) => s.replace(/'/g, "''");

const platform = process.platform;
const done = () => process.exit(0);

if (platform === 'darwin') {
  const chime = process.env.CLAUDE_ALERT_CHIME || '/System/Library/Sounds/Glass.aiff';
  const sayArgs = VOICE ? ['-v', VOICE, MESSAGE] : [MESSAGE];
  // chime first, then speak
  tryFirst([{ cmd: 'afplay', args: [chime] }], () => {
    tryFirst([{ cmd: 'say', args: sayArgs }], done);
  });
} else if (platform === 'win32') {
  const selectVoice = VOICE ? `$s.SelectVoice('${psQuote(VOICE)}');` : '';
  const ps = [
    'Add-Type -AssemblyName System.Speech;',
    '[console]::beep(880,150);',
    '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;',
    selectVoice,
    `$s.Speak('${psQuote(MESSAGE)}');`,
  ].join(' ');
  tryFirst(
    [
      { cmd: 'powershell', args: ['-NoProfile', '-Command', ps] },
      { cmd: 'pwsh', args: ['-NoProfile', '-Command', ps] },
    ],
    done
  );
} else {
  // Linux / other Unix
  const chime = process.env.CLAUDE_ALERT_CHIME || '';
  const playChime = (next) => {
    if (!chime) return next();
    tryFirst(
      [
        { cmd: 'paplay', args: [chime] },
        { cmd: 'aplay', args: [chime] },
      ],
      next
    );
  };
  const speak = () =>
    tryFirst(
      [
        { cmd: 'spd-say', args: ['--wait', MESSAGE] },
        { cmd: 'espeak', args: [MESSAGE] },
      ],
      done
    );
  playChime(speak);
}
