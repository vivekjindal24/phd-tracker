package edu.university.phdtracker.service;

import edu.university.phdtracker.dto.AuthRequest;
import edu.university.phdtracker.dto.AuthResponse;
import edu.university.phdtracker.dto.RegisterUserRequest;

public interface AuthService {

    AuthResponse login(AuthRequest request);

    AuthResponse register(RegisterUserRequest request);
}

