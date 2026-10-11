package edu.university.phdtracker.dto;

import edu.university.phdtracker.entity.Role;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record RegisterUserRequest(
        @NotBlank(message = "Name is required")
        String name,

        @Email(message = "Email must be valid")
        @NotBlank(message = "Email is required")
        String email,

        @NotBlank(message = "Password is required")
        String password,

        @NotNull(message = "Role is required")
        Role role,

        @NotBlank(message = "WhatsApp number is required")
        String whatsappNumber,

        String department
) {
}
