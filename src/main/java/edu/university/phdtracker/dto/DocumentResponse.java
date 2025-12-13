package edu.university.phdtracker.dto;

import java.time.Instant;

public record DocumentResponse(
        Long id,
        String fileName,
        String version,
        Instant uploadedAt
) {
}

