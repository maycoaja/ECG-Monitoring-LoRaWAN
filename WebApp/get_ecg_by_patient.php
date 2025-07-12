<?php
header('Content-Type: application/json');
require 'db_connect.php';

$id = $_GET['id'] ?? null;

if (!$id) {
    http_response_code(400);
    echo json_encode(['error' => 'No patient ID']);
    exit;
}

try {
    $stmt = $pdo->prepare("SELECT value FROM ecg_data WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 500");
    $stmt->execute([$id]);
    $values = array_column($stmt->fetchAll(PDO::FETCH_ASSOC), 'value');
    echo json_encode($values);
} catch (PDOException $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>
