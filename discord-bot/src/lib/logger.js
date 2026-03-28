/**
 * Minimal structured logger.
 */

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };
const MIN_LEVEL = LEVELS[process.env.LOG_LEVEL ?? 'info'] ?? 1;

function emit(level, msg, data) {
  if (LEVELS[level] < MIN_LEVEL) return;
  const line = { ts: new Date().toISOString(), level, msg, ...data };
  (level === 'error' || level === 'warn' ? console.error : console.log)(JSON.stringify(line));
}

const log = {
  debug: (msg, data = {}) => emit('debug', msg, data),
  info:  (msg, data = {}) => emit('info',  msg, data),
  warn:  (msg, data = {}) => emit('warn',  msg, data),
  error: (msg, data = {}) => emit('error', msg, data),
};

export default log;
