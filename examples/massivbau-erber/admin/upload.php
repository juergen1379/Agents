<?php
/* Nimmt ein Bild entgegen, prüft es, verkleinert es und legt es in assets/uploads ab */
declare(strict_types=1);
require __DIR__ . '/lib.php';
start_session();
require_login();

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !check_csrf($_POST['csrf'] ?? null)) {
    json_out(['ok' => false, 'error' => 'Die Sitzung ist abgelaufen. Bitte die Seite neu laden.'], 403);
}
$f = $_FILES['image'] ?? null;
if (!$f || !is_uploaded_file($f['tmp_name'] ?? '') || ($f['error'] ?? 1) !== UPLOAD_ERR_OK) {
    json_out(['ok' => false, 'error' => 'Das Bild ist nicht angekommen. Vielleicht ist die Datei zu groß.'], 400);
}
if ($f['size'] > MAX_UPLOAD_BYTES) { json_out(['ok' => false, 'error' => 'Das Bild ist größer als 12 MB.'], 400); }

$info = @getimagesize($f['tmp_name']);
$types = [IMAGETYPE_JPEG => 'jpg', IMAGETYPE_PNG => 'png', IMAGETYPE_WEBP => 'webp'];
if (!$info || !isset($types[$info[2]])) { json_out(['ok' => false, 'error' => 'Bitte ein JPG, PNG oder WebP wählen.'], 400); }
if ($info[0] * $info[1] > 60000000) { json_out(['ok' => false, 'error' => 'Das Bild hat zu viele Bildpunkte.'], 400); }

if (!is_dir(UPLOAD_DIR) && !mkdir(UPLOAD_DIR, 0755, true)) { json_out(['ok' => false, 'error' => 'Der Upload-Ordner fehlt.'], 500); }
$base = 'bild-' . date('Ymd') . '-' . bin2hex(random_bytes(6));

if (function_exists('imagecreatefromstring')) {
    @ini_set('memory_limit', '512M');
    $img = @imagecreatefromstring((string) file_get_contents($f['tmp_name']));
    if (!$img) { json_out(['ok' => false, 'error' => 'Das Bild konnte nicht gelesen werden.'], 400); }

    // Handyfotos richtig herum drehen
    if ($info[2] === IMAGETYPE_JPEG && function_exists('exif_read_data')) {
        $exif = @exif_read_data($f['tmp_name']);
        $turn = [3 => 180, 6 => -90, 8 => 90][$exif['Orientation'] ?? 0] ?? 0;
        if ($turn) { $img = imagerotate($img, $turn, 0); }
    }
    $w = imagesx($img); $h = imagesy($img);
    if ($w > MAX_IMAGE_WIDTH) {
        $nh = (int) round($h * MAX_IMAGE_WIDTH / $w);
        $small = imagecreatetruecolor(MAX_IMAGE_WIDTH, $nh);
        imagealphablending($small, false); imagesavealpha($small, true);
        imagecopyresampled($small, $img, 0, 0, 0, 0, MAX_IMAGE_WIDTH, $nh, $w, $h);
        $img = $small; $w = MAX_IMAGE_WIDTH; $h = $nh;
    }
    if (function_exists('imagewebp')) {
        imagepalettetotruecolor($img); imagesavealpha($img, true);
        $name = $base . '.webp';
        $ok = imagewebp($img, UPLOAD_DIR . '/' . $name, 80);
    } else {
        $flat = imagecreatetruecolor($w, $h);
        imagefill($flat, 0, 0, imagecolorallocate($flat, 255, 255, 255));
        imagecopy($flat, $img, 0, 0, 0, 0, $w, $h);
        $name = $base . '.jpg';
        $ok = imagejpeg($flat, UPLOAD_DIR . '/' . $name, 84);
    }
    if (!$ok) { json_out(['ok' => false, 'error' => 'Das Bild konnte nicht gespeichert werden.'], 500); }
} else {
    // Ohne Bildbibliothek: geprüfte Datei unverändert ablegen
    $name = $base . '.' . $types[$info[2]];
    if (!move_uploaded_file($f['tmp_name'], UPLOAD_DIR . '/' . $name)) {
        json_out(['ok' => false, 'error' => 'Das Bild konnte nicht gespeichert werden.'], 500);
    }
    $w = $info[0]; $h = $info[1];
}
@chmod(UPLOAD_DIR . '/' . $name, 0644);
json_out(['ok' => true, 'src' => 'assets/uploads/' . $name, 'width' => $w, 'height' => $h]);
