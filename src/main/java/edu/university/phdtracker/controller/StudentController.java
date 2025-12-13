package edu.university.phdtracker.controller;

import edu.university.phdtracker.dto.DocumentResponse;
import edu.university.phdtracker.dto.DocumentUploadRequest;
import edu.university.phdtracker.dto.MilestoneResponse;
import edu.university.phdtracker.dto.MilestoneUpdateRequest;
import edu.university.phdtracker.dto.NotificationResponse;
import edu.university.phdtracker.security.UserPrincipal;
import edu.university.phdtracker.service.StudentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/student")
@RequiredArgsConstructor
@Validated
public class StudentController {

    private final StudentService studentService;

    @PutMapping("/milestones/{id}")
    @PreAuthorize("hasRole('STUDENT')")
    public ResponseEntity<MilestoneResponse> updateMilestone(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id,
            @Valid @RequestBody MilestoneUpdateRequest request) {
        return ResponseEntity.ok(studentService.updateMilestoneProgress(principal.id(), id, request));
    }

    @PostMapping("/documents")
    @PreAuthorize("hasRole('STUDENT')")
    public ResponseEntity<DocumentResponse> uploadDocument(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody DocumentUploadRequest request) {
        return ResponseEntity.ok(studentService.uploadDocument(principal.id(), request));
    }

    @GetMapping("/notifications")
    @PreAuthorize("hasRole('STUDENT')")
    public ResponseEntity<List<NotificationResponse>> getNotifications(
            @AuthenticationPrincipal UserPrincipal principal) {
        return ResponseEntity.ok(studentService.getNotifications(principal.id()));
    }
}

