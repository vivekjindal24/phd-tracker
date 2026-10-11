package edu.university.phdtracker.dto;

import edu.university.phdtracker.entity.NotificationChannel;

import java.time.Instant;

public record NotificationResponse(
        Long id,
        String message,
        NotificationChannel channel,
        Instant sentAt
) {
}

