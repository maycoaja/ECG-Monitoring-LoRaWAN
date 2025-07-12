<?php
header('Content-Type: application/json');
require 'db_connect.php';

$id = $_GET['id'] ?? null;

if (!$id) {
    http_response_code(400);
    echo json_encode(['status' => 'error', 'message' => 'ID tidak dikirim']);
    exit;
}

try {
    $pdo->prepare("DELETE FROM ecg_data WHERE patient_id = ?")->execute([$id]);
    $pdo->prepare("DELETE FROM heart_rate WHERE patient_id = ?")->execute([$id]);

    $stmt = $pdo->prepare("DELETE FROM patients WHERE id = ?");
    $stmt->execute([$id]);

    echo json_encode(['status' => 'success']);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
}
?>
