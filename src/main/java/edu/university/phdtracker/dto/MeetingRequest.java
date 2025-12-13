package edu.university.phdtracker.dto;

import jakarta.validation.constraints.Future;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.Instant;

public record MeetingRequest(
        @NotNull(message = "Supervisor ID is required")
        Long supervisorId,

        @NotNull(message = "Student ID is required")
        Long studentId,

        @NotNull(message = "Meeting date is required")
        @Future(message = "Meeting date must be in the future")
        Instant meetingDate,

        @NotBlank(message = "Agenda is required")
        String agenda
) {
}

