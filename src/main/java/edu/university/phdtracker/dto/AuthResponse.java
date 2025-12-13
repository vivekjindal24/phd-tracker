package edu.university.phdtracker.dto;

public record AuthResponse(String token, String role, Long userId) {
}

