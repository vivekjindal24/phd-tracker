package edu.university.phdtracker.service.impl;

import edu.university.phdtracker.dto.DocumentResponse;
import edu.university.phdtracker.dto.MeetingRequest;
import edu.university.phdtracker.dto.MeetingResponse;
import edu.university.phdtracker.dto.SupervisorReportResponse;
import edu.university.phdtracker.dto.SupervisorStudentRequest;
import edu.university.phdtracker.dto.SupervisorStudentResponse;
import edu.university.phdtracker.entity.Document;
import edu.university.phdtracker.entity.Meeting;
import edu.university.phdtracker.entity.Milestone;
import edu.university.phdtracker.entity.Student;
import edu.university.phdtracker.entity.Supervisor;
import edu.university.phdtracker.entity.User;
import edu.university.phdtracker.exception.PhdTrackerException;
import edu.university.phdtracker.exception.ResourceNotFoundException;
import edu.university.phdtracker.integration.GoogleCalendarService;
import edu.university.phdtracker.repository.DocumentRepository;
import edu.university.phdtracker.repository.MeetingRepository;
import edu.university.phdtracker.dto.MilestoneResponse;
import edu.university.phdtracker.repository.MilestoneRepository;
import edu.university.phdtracker.repository.StudentRepository;
import edu.university.phdtracker.repository.SupervisorRepository;
import edu.university.phdtracker.repository.UserRepository;
import edu.university.phdtracker.service.SupervisorService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional
public class SupervisorServiceImpl implements SupervisorService {

    private final SupervisorRepository supervisorRepository;
    private final StudentRepository studentRepository;
    private final UserRepository userRepository;
    private final MeetingRepository meetingRepository;
    private final MilestoneRepository milestoneRepository;
    private final DocumentRepository documentRepository;
    private final GoogleCalendarService googleCalendarService;

    @Override
    public SupervisorStudentResponse addStudent(Long supervisorId, SupervisorStudentRequest request) {
        Supervisor supervisor = supervisorRepository.findById(supervisorId)
                .orElseThrow(() -> new ResourceNotFoundException("Supervisor not found"));
        User studentUser = userRepository.findById(request.userId())
                .orElseThrow(() -> new ResourceNotFoundException("User not found"));
        if (!studentUser.getRole().name().equals("STUDENT")) {
            throw new PhdTrackerException("User must have STUDENT role");
        }
        if (studentRepository.existsByUserId(studentUser.getId())) {
            throw new PhdTrackerException("Student already assigned");
        }
        Student student = Student.builder()
                .user(studentUser)
                .supervisor(supervisor)
                .researchTitle(request.researchTitle())
                .status(request.status())
                .enrollmentDate(request.enrollmentDate())
                .build();
        studentRepository.save(student);
        return mapStudent(student);
    }

    @Override
    @Transactional(readOnly = true)
    public List<SupervisorStudentResponse> getStudents(Long supervisorId) {
        return studentRepository.findBySupervisorId(supervisorId)
                .stream()
                .map(this::mapStudent)
                .collect(Collectors.toList());
    }

    @Override
    public MeetingResponse scheduleMeeting(MeetingRequest request) {
        Supervisor supervisor = supervisorRepository.findById(request.supervisorId())
                .orElseThrow(() -> new ResourceNotFoundException("Supervisor not found"));
        Student student = studentRepository.findById(request.studentId())
                .orElseThrow(() -> new ResourceNotFoundException("Student not found"));
        if (!student.getSupervisor().getId().equals(supervisor.getId())) {
            throw new PhdTrackerException("Student is not assigned to this supervisor");
        }
        Meeting meeting = Meeting.builder()
                .supervisor(supervisor)
                .student(student)
                .meetingDate(request.meetingDate())
                .agenda(request.agenda())
                .build();
        meeting = meetingRepository.save(meeting);
        String googleEventId = googleCalendarService.createMeetingEvent(
                supervisor.getUser().getEmail(),
                student.getUser().getEmail(),
                request.meetingDate(),
                request.agenda()
        );
        meeting.setGoogleEventId(googleEventId);
        meetingRepository.save(meeting);
        return mapMeeting(meeting);
    }

    @Override
    @Transactional(readOnly = true)
    public SupervisorReportResponse generateReport(Long supervisorId, Long studentId) {
        Supervisor supervisor = supervisorRepository.findById(supervisorId)
                .orElseThrow(() -> new ResourceNotFoundException("Supervisor not found"));
        Student student = studentRepository.findById(studentId)
                .orElseThrow(() -> new ResourceNotFoundException("Student not found"));
        if (!student.getSupervisor().getId().equals(supervisor.getId())) {
            throw new PhdTrackerException("Student is not assigned to this supervisor");
        }
        List<Milestone> milestones = milestoneRepository.findByStudentId(studentId);
        List<Document> documents = documentRepository.findByStudentId(studentId);
        List<Meeting> meetings = meetingRepository.findByStudentId(studentId);
        return new SupervisorReportResponse(
                student.getId(),
                student.getUser().getName(),
                student.getResearchTitle(),
                student.getStatus(),
                milestones.stream().map(this::mapMilestone).collect(Collectors.toList()),
                documents.stream().map(this::mapDocument).collect(Collectors.toList()),
                meetings.stream().map(this::mapMeeting).collect(Collectors.toList())
        );
    }

    private SupervisorStudentResponse mapStudent(Student student) {
        User user = student.getUser();
        return new SupervisorStudentResponse(
                student.getId(),
                user.getId(),
                user.getName(),
                user.getEmail(),
                student.getResearchTitle(),
                student.getStatus(),
                student.getEnrollmentDate()
        );
    }

    private MeetingResponse mapMeeting(Meeting meeting) {
        return new MeetingResponse(
                meeting.getId(),
                meeting.getSupervisor().getId(),
                meeting.getStudent().getId(),
                meeting.getMeetingDate(),
                meeting.getAgenda(),
                meeting.getGoogleEventId()
        );
    }

    private MilestoneResponse mapMilestone(Milestone milestone) {
        return new MilestoneResponse(
                milestone.getId(),
                milestone.getTitle(),
                milestone.getDescription(),
                milestone.getDeadline(),
                milestone.getStatus(),
                milestone.getCreatedAt()
        );
    }

    private DocumentResponse mapDocument(Document document) {
        return new DocumentResponse(
                document.getId(),
                document.getFileName(),
                document.getVersion(),
                document.getUploadedAt()
        );
    }
}
