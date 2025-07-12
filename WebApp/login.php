<?php
header('Content-Type: application/json');
require 'db_connect.php';

$data = json_decode(file_get_contents("php://input"), true);
$username = $data['username'] ?? '';
$password = $data['password'] ?? '';

try {
    $stmt = $pdo->prepare("SELECT * FROM users WHERE username = ?");
    $stmt->execute([$username]);
    $user = $stmt->fetch(PDO::FETCH_ASSOC);

    if ($user) {
        // Cek password (pastikan php punya fungsi password_verify)
        if (password_verify($password, $user['password'])) {
            echo json_encode(["status" => "success"]);
        } else {
            echo json_encode(["status" => "failed", "message" => "Password salah"]);
        }
    } else {
        echo json_encode(["status" => "failed", "message" => "User tidak ditemukan"]);
    }
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(["error" => "Query error: " . $e->getMessage()]);
    // kamu bisa juga log ke file dengan file_put_contents('error.log', $e->getMessage());
}