package edu.university.phdtracker.service.impl;

import edu.university.phdtracker.dto.AuthRequest;
import edu.university.phdtracker.dto.AuthResponse;
import edu.university.phdtracker.dto.RegisterUserRequest;
import edu.university.phdtracker.entity.User;
import edu.university.phdtracker.entity.Supervisor;
import edu.university.phdtracker.entity.Role;
import edu.university.phdtracker.entity.Student;
import edu.university.phdtracker.exception.PhdTrackerException;
import edu.university.phdtracker.repository.UserRepository;
import edu.university.phdtracker.repository.SupervisorRepository;
import edu.university.phdtracker.repository.StudentRepository;
import edu.university.phdtracker.security.JwtService;
import edu.university.phdtracker.service.AuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final AuthenticationManager authenticationManager;
    private final SupervisorRepository supervisorRepository;
    private final StudentRepository studentRepository;

    @Override
    public AuthResponse login(AuthRequest request) {
        authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.email(), request.password())
        );
        User user = userRepository.findByEmail(request.email())
                .orElseThrow(() -> new PhdTrackerException("Invalid credentials"));
        String token = jwtService.generateToken(user);
        return new AuthResponse(token, user.getRole().name(), user.getId());
    }

    @Override
    @Transactional
    public AuthResponse register(RegisterUserRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new PhdTrackerException("Email already registered");
        }
        User user = User.builder()
                .name(request.name())
                .email(request.email())
                .password(passwordEncoder.encode(request.password()))
                .role(request.role())
                .whatsappNumber(request.whatsappNumber())
                .build();
        userRepository.save(user);

        if (Role.SUPERVISOR.equals(request.role())) {
            Supervisor supervisor = Supervisor.builder()
                    .user(user)
                    .department(Optional.ofNullable(request.department()).orElse("UNKNOWN"))
                    .build();
            supervisorRepository.save(supervisor);
        } else if (Role.STUDENT.equals(request.role())) {
            if (studentRepository.existsByUserId(user.getId())) {
                throw new PhdTrackerException("Student already exists for this user");
            }
            Student student = Student.builder()
                    .user(user)
                    .researchTitle("TBD")
                    .status("PENDING")
                    .enrollmentDate(Instant.now())
                    .build();
            studentRepository.save(student);
        }

        String token = jwtService.generateToken(user);
        return new AuthResponse(token, user.getRole().name(), user.getId());
    }
}
