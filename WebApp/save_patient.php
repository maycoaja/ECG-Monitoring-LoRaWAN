<?php
header('Content-Type: application/json');
require 'db_connect.php';

$data = json_decode(file_get_contents("php://input"), true);

if (!$data) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid data']);
    exit;
}

$name = $data['name'] ?? '';
$age = $data['age'] ?? null;
$gender = $data['gender'] ?? '';
$mrn = $data['mrn'] ?? '';
$condition = $data['condition'] ?? '';
$notes = $data['notes'] ?? '';
$device_id = $data['device_id'] ?? '';
$slot_number = $data['slot_number'] ?? null;
$id = $data['id'] ?? null;

try {
    if ($id) {
        // Mode EDIT: pastikan device tidak dipakai pasien lain
        $checkDup = $pdo->prepare("SELECT id FROM patients WHERE device_id = ? AND id != ?");
        $checkDup->execute([$device_id, $id]);
        if ($checkDup->rowCount() > 0) {
            echo json_encode(['status' => 'error', 'message' => 'Device sudah dipakai pasien lain.']);
            exit;
        }

        $stmt = $pdo->prepare("UPDATE patients SET name = ?, age = ?, gender = ?, mrn = ?, condition = ?, notes = ?, device_id = ?, slot_number = ? WHERE id = ?");
        $stmt->execute([$name, $age, $gender, $mrn, $condition, $notes, $device_id, $slot_number, $id]);


    } else {
        // Mode INSERT: pastikan device belum dipakai
        $checkDup = $pdo->prepare("SELECT id FROM patients WHERE device_id = ?");
        $checkDup->execute([$device_id]);
        if ($checkDup->rowCount() > 0) {
            echo json_encode(['status' => 'error', 'message' => 'Device sudah dipakai pasien lain.']);
            exit;
        }

        $stmt = $pdo->prepare("INSERT INTO patients (name, age, gender, mrn, condition, notes, device_id, slot_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
        $stmt->execute([$name, $age, $gender, $mrn, $condition, $notes, $device_id, $slot_number]);

        $id = $pdo->lastInsertId();
    }

    echo json_encode(['status' => 'success', 'id' => $id]);

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
}
