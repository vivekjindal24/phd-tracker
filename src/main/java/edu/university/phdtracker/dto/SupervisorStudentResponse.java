package edu.university.phdtracker.dto;

import java.time.Instant;

public record SupervisorStudentResponse(
        Long studentId,
        Long userId,
        String name,
        String email,
        String researchTitle,
        String status,
        Instant enrollmentDate
) {
}

