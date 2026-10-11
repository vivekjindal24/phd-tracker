package edu.university.phdtracker.dto;

import edu.university.phdtracker.entity.NotificationChannel;

import java.time.Instant;

public record StudentNotificationResponse(
        Long id,
        String message,
        NotificationChannel channel,
        Instant sentAt
) {
}

