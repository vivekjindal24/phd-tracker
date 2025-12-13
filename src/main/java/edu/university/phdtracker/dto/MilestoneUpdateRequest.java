package edu.university.phdtracker.dto;

import edu.university.phdtracker.entity.MilestoneStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record MilestoneUpdateRequest(
        @NotBlank(message = "Title is required")
        String title,

        @NotBlank(message = "Description is required")
        String description,

        @NotNull(message = "Status is required")
        MilestoneStatus status
) {
}

