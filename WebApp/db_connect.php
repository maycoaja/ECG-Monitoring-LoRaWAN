<?php
// db_connect.php

$host = 'localhost';
$port = '5432';
$dbname = 'ecg_monitoring';
$user = 'admin';
$pass = 'xxx';

try {
    $pdo = new PDO("pgsql:host=$host;port=$port;dbname=$dbname", $user, $pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);
} catch (PDOException $e) {
    error_log("DB Connection Error: " . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Internal server error.']);
    exit;
}
