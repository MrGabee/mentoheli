<?php
// Számla Figyelő - azonnali futtatás indítója (a "Küldés MOST" gombokhoz).
//
// A GitHub token CSAK itt, a szerveren van (futtatas_config.php), a
// böngésző soha nem látja. A dashboard a bejelentkezéskor kapott
// api-kulccsal hívja ezt a fájlt; az api-kulcsot és a dashboardon lévő
// "Azonnali indítás" kapcsolót az api.php-tól kérdezzük le (get_meta),
// így ennek a fájlnak nem kell ismernie az adatbázist.
//
// Telepítés: ezt a fájlt és a kitöltött futtatas_config.php-t töltsd fel
// az api.php mellé (reilviolin.hu/billing/).

$ENGEDETT_ORIGINEK = ["https://mrgabee.github.io"];
$origin = $_SERVER["HTTP_ORIGIN"] ?? "";
if (in_array($origin, $ENGEDETT_ORIGINEK, true)) {
    header("Access-Control-Allow-Origin: " . $origin);
    header("Vary: Origin");
    header("Access-Control-Allow-Methods: POST, OPTIONS");
    header("Access-Control-Allow-Headers: Content-Type");
}
header("Content-Type: application/json; charset=utf-8");

function valasz($kod, $adat) {
    http_response_code($kod);
    echo json_encode($adat, JSON_UNESCAPED_UNICODE);
    exit;
}

if ($_SERVER["REQUEST_METHOD"] === "OPTIONS") valasz(204, []);
if ($_SERVER["REQUEST_METHOD"] !== "POST") valasz(405, ["ok" => false, "hiba" => "Csak POST."]);

$konfig_fajl = __DIR__ . "/futtatas_config.php";
if (!is_file($konfig_fajl)) valasz(500, ["ok" => false, "hiba" => "Hiányzik a futtatas_config.php a szerverről."]);
$konfig = require $konfig_fajl;
$token = trim($konfig["github_token"] ?? "");
if ($token === "" || strpos($token, "IDE_") === 0) valasz(500, ["ok" => false, "hiba" => "A futtatas_config.php-ban nincs megadva a GitHub token."]);
$api_url = $konfig["api_url"] ?? "https://reilviolin.hu/billing/api.php";

$keres = json_decode(file_get_contents("php://input"), true);
$api_kulcs = is_array($keres) ? (string)($keres["api_kulcs"] ?? "") : "";
if ($api_kulcs === "") valasz(401, ["ok" => false, "hiba" => "Hiányzik az api-kulcs."]);

// workflow_dispatch inputok: csak egyszerű szöveges értékek mehetnek tovább.
$inputs = [];
foreach ((is_array($keres["inputs"] ?? null) ? $keres["inputs"] : []) as $k => $v) {
    if (!preg_match('/^[a-z0-9_]{1,64}$/', (string)$k)) continue;
    if (!is_scalar($v)) continue;
    $inputs[$k] = substr((string)$v, 0, 2000);
}

function json_post($url, $torzs, $fejlecek) {
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($torzs),
        CURLOPT_HTTPHEADER => $fejlecek,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 20,
    ]);
    $szoveg = curl_exec($ch);
    $kod = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [$kod, $szoveg];
}

// 1) Api-kulcs ellenőrzése + a kapcsoló állása, egy hívással.
[$kod, $szoveg] = json_post($api_url, ["action" => "get_meta", "api_kulcs" => $api_kulcs, "kulcs" => "azonnali_inditas"], ["Content-Type: application/json"]);
$meta = json_decode((string)$szoveg, true);
if ($kod !== 200 || !is_array($meta) || empty($meta["ok"])) valasz(401, ["ok" => false, "hiba" => "Érvénytelen api-kulcs."]);
$kapcsolo = $meta["ertek"] ?? null;
if (is_array($kapcsolo) && array_key_exists("be", $kapcsolo) && !$kapcsolo["be"]) {
    valasz(409, ["ok" => false, "kikapcsolva" => true, "hiba" => "Az azonnali indítás ki van kapcsolva a dashboardon."]);
}

// 2) A futás elindítása. A tároló és a workflow itt rögzített.
$gh_url = "https://api.github.com/repos/MrGabee/mentoheli/actions/workflows/szamla_monitor.yml/dispatches";
$torzs = ["ref" => "main"];
if ($inputs) $torzs["inputs"] = $inputs;
[$kod, $szoveg] = json_post($gh_url, $torzs, [
    "Accept: application/vnd.github+json",
    "Authorization: Bearer " . $token,
    "X-GitHub-Api-Version: 2022-11-28",
    "User-Agent: szamla-figyelo",
    "Content-Type: application/json",
]);
if ($kod !== 204) valasz(502, ["ok" => false, "hiba" => "A GitHub nem indította el a futást (HTTP " . $kod . "): " . substr((string)$szoveg, 0, 200)]);
valasz(200, ["ok" => true]);
