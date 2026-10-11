package edu.university.phdtracker.controller;

import edu.university.phdtracker.dto.MeetingRequest;
import edu.university.phdtracker.dto.MeetingResponse;
import edu.university.phdtracker.dto.SupervisorReportResponse;
import edu.university.phdtracker.dto.SupervisorStudentRequest;
import edu.university.phdtracker.dto.SupervisorStudentResponse;
import edu.university.phdtracker.security.UserPrincipal;
import edu.university.phdtracker.service.SupervisorService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/supervisor")
@Validated
@RequiredArgsConstructor
public class SupervisorController {

    private final SupervisorService supervisorService;

    @PostMapping("/students")
    @PreAuthorize("hasRole('SUPERVISOR')")
    public ResponseEntity<SupervisorStudentResponse> addStudent(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody SupervisorStudentRequest request) {
        return ResponseEntity.ok(supervisorService.addStudent(principal.id(), request));
    }

    @GetMapping("/students")
    @PreAuthorize("hasRole('SUPERVISOR')")
    public ResponseEntity<List<SupervisorStudentResponse>> getStudents(
            @AuthenticationPrincipal UserPrincipal principal) {
        return ResponseEntity.ok(supervisorService.getStudents(principal.id()));
    }

    @PostMapping("/meetings")
    @PreAuthorize("hasRole('SUPERVISOR')")
    public ResponseEntity<MeetingResponse> scheduleMeeting(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody MeetingRequest request) {
        MeetingRequest enriched = new MeetingRequest(principal.id(), request.studentId(), request.meetingDate(), request.agenda());
        return ResponseEntity.ok(supervisorService.scheduleMeeting(enriched));
    }

    @GetMapping("/reports/{studentId}")
    @PreAuthorize("hasRole('SUPERVISOR')")
    public ResponseEntity<SupervisorReportResponse> getReport(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long studentId) {
        return ResponseEntity.ok(supervisorService.generateReport(principal.id(), studentId));
    }
}
