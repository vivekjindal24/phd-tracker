package edu.university.phdtracker.dto;

import jakarta.validation.constraints.NotBlank;

public record DocumentUploadRequest(
        @NotBlank(message = "File name is required")
        String fileName,

        @NotBlank(message = "Version is required")
        String version
) {
}
