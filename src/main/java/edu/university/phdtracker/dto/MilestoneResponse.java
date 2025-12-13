package edu.university.phdtracker.dto;

import edu.university.phdtracker.entity.MilestoneStatus;

import java.time.Instant;
import java.time.LocalDate;

public record MilestoneResponse(
        Long id,
        String title,
        String description,
        LocalDate deadline,
        MilestoneStatus status,
        Instant createdAt
) {
}

