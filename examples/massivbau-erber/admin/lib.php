<?php
/* Massivbau Erber · Bearbeitungsbereich: gemeinsame Funktionen.
   Die Seite selbst bleibt eine statische index.html. Der Bearbeitungsbereich
   ändert darin nur Stellen, die mit data-edit oder data-edit-img markiert sind. */

declare(strict_types=1);

const SITE_FILE   = __DIR__ . '/../index.html';
const DATA_DIR    = __DIR__ . '/data';
const BACKUP_DIR  = __DIR__ . '/data/backups';
const UPLOAD_DIR  = __DIR__ . '/../assets/uploads';
const CONFIG_FILE = __DIR__ . '/data/config.php';
const TRIES_FILE  = __DIR__ . '/data/attempts.php';
const MAX_BACKUPS = 30;
const MAX_TRIES   = 5;
const LOCK_SECONDS = 900;
const IDLE_SECONDS = 3600;
const MAX_UPLOAD_BYTES = 12 * 1024 * 1024;
const MAX_IMAGE_WIDTH = 1600;
const MAX_TEXT_LENGTH = 3000;

header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: same-origin');
header('Cache-Control: no-store');

function start_session(): void {
    $secure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
    session_name('erber_admin');
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? '/admin/x'), '/') . '/',
        'secure' => $secure,
        'httponly' => true,
        'samesite' => 'Strict',
    ]);
    session_start();
    if (isset($_SESSION['seen']) && time() - $_SESSION['seen'] > IDLE_SECONDS) {
        $_SESSION = [];
        session_regenerate_id(true);
    }
    $_SESSION['seen'] = time();
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
}

function config(): ?array {
    if (!is_file(CONFIG_FILE)) return null;
    $c = include CONFIG_FILE;
    return is_array($c) && !empty($c['password_hash']) ? $c : null;
}

function save_config(string $hash): bool {
    $php = "<?php\nreturn " . var_export(['password_hash' => $hash], true) . ";\n";
    return write_atomic(CONFIG_FILE, $php);
}

function write_atomic(string $file, string $content): bool {
    $tmp = $file . '.' . bin2hex(random_bytes(6)) . '.tmp';
    if (file_put_contents($tmp, $content, LOCK_EX) === false) return false;
    if (!rename($tmp, $file)) { @unlink($tmp); return false; }
    return true;
}

function logged_in(): bool { return !empty($_SESSION['auth']); }

function require_login(): void {
    if (!logged_in()) { json_out(['ok' => false, 'error' => 'Bitte neu anmelden.'], 401); }
}

function csrf(): string { return $_SESSION['csrf']; }

function check_csrf(?string $token): bool {
    return is_string($token) && hash_equals($_SESSION['csrf'] ?? '', $token);
}

function json_out(array $data, int $status = 200): never {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function e(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }

function password_problem(string $pw, string $again): ?string {
    if ($pw !== $again) return 'Die beiden Passwörter stimmen nicht überein.';
    if (mb_strlen($pw) < 12) return 'Das Passwort braucht mindestens 12 Zeichen.';
    return null;
}

/* ---------- Anmeldeversuche begrenzen (pro IP-Adresse) ---------- */
function tries_read(): array {
    if (!is_file(TRIES_FILE)) return [];
    $raw = (string) file_get_contents(TRIES_FILE);
    $json = substr($raw, (int) strpos($raw, "\n") + 1);
    $data = json_decode($json, true);
    return is_array($data) ? $data : [];
}
function tries_write(array $data): void {
    $now = time();
    $data = array_filter($data, fn($t) => $now - ($t['last'] ?? 0) < LOCK_SECONDS);
    write_atomic(TRIES_FILE, "<?php exit; ?>\n" . json_encode($data));
}
function client_key(): string { return hash('sha256', $_SERVER['REMOTE_ADDR'] ?? 'unknown'); }
function locked_seconds(): int {
    $t = tries_read()[client_key()] ?? null;
    if (!$t || $t['count'] < MAX_TRIES) return 0;
    return max(0, LOCK_SECONDS - (time() - $t['last']));
}
function note_failure(): void {
    $data = tries_read(); $k = client_key();
    $data[$k] = ['count' => ($data[$k]['count'] ?? 0) + 1, 'last' => time()];
    tries_write($data);
}
function clear_failures(): void {
    $data = tries_read(); unset($data[client_key()]); tries_write($data);
}

/* ---------- Sicherungen ---------- */
function make_backup(): bool {
    if (!is_dir(BACKUP_DIR) && !mkdir(BACKUP_DIR, 0755, true)) return false;
    $name = 'index-' . date('Ymd-His') . '-' . bin2hex(random_bytes(4)) . '.html';
    if (!copy(SITE_FILE, BACKUP_DIR . '/' . $name)) return false;
    $all = list_backups();
    foreach (array_slice($all, MAX_BACKUPS) as $old) { @unlink(BACKUP_DIR . '/' . $old); }
    return true;
}
function list_backups(): array {
    $files = array_map('basename', glob(BACKUP_DIR . '/index-*.html') ?: []);
    rsort($files);
    return $files;
}
function backup_label(string $file): string {
    if (!preg_match('/^index-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})-[0-9a-f]{8}\.html$/', $file, $m)) return $file;
    return "$m[3].$m[2].$m[1], $m[4]:$m[5] Uhr";
}

/* ---------- Änderungen in die Seite schreiben ---------- */
function clean_text(string $text): string {
    $text = preg_replace('/\s+/u', ' ', $text) ?? '';
    $text = trim($text);
    return str_replace(['&', '<', '>'], ['&amp;', '&lt;', '&gt;'], $text);
}

/** Ersetzt den Inhalt aller Elemente mit data-edit="$key". Liefert die Zahl der Treffer. */
function set_text(string &$html, string $key, string $safe): int {
    $pattern = '~(<([a-z0-9]+)\b[^<>]*\sdata-edit="' . preg_quote($key, '~') . '"[^<>]*>)[^<>]*(</\2>)~u';
    $count = 0;
    $new = preg_replace_callback($pattern, fn($m) => $m[1] . $safe . $m[3], $html, -1, $count);
    if ($new !== null && $count > 0) $html = $new;
    return $count;
}

/** Setzt src, alt, width und height des Bildes mit data-edit-img="$key". */
function set_image(string &$html, string $key, ?string $src, ?string $alt, ?int $w, ?int $h): int {
    $pattern = '~<img\b[^<>]*\sdata-edit-img="' . preg_quote($key, '~') . '"[^<>]*>~u';
    $count = 0;
    $new = preg_replace_callback($pattern, function ($m) use ($src, $alt, $w, $h) {
        $tag = $m[0];
        $set = function (string $tag, string $name, string $value): string {
            $attr = $name . '="' . e($value) . '"';
            $n = 0;
            $out = preg_replace('~\s' . $name . '="[^"]*"~u', ' ' . $attr, $tag, 1, $n);
            return $n ? $out : preg_replace('~^<img~', '<img ' . $attr, $tag, 1);
        };
        if ($src !== null) $tag = $set($tag, 'src', $src);
        if ($alt !== null) $tag = $set($tag, 'alt', $alt);
        if ($w && $h) { $tag = $set($tag, 'width', (string) $w); $tag = $set($tag, 'height', (string) $h); }
        return $tag;
    }, $html, -1, $count);
    if ($new !== null && $count > 0) $html = $new;
    return $count;
}
