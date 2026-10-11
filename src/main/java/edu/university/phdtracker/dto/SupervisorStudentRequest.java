package edu.university.phdtracker.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;

public record SupervisorStudentRequest(
        @NotNull(message = "User ID is required")
        Long userId,

        @NotBlank(message = "Research title is required")
        String researchTitle,

        @NotBlank(message = "Status is required")
        String status,

        @NotNull(message = "Enrollment date is required")
        Instant enrollmentDate
) {
}

