package com.nmdw.ansimon.elderly.application;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.dto.ElderlyRegisterRequest;
import com.nmdw.ansimon.elderly.dto.ElderlyUpdateRequest;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ElderlyServiceTest {

    private final ElderlyProfileRepository repository = mock(ElderlyProfileRepository.class);
    private final GeocodingClient geocodingClient = mock(GeocodingClient.class);
    private final ElderlyService service = new ElderlyService(repository, geocodingClient);

    @Test
    void registersAProfileAfterGeocodingAndListsItWithFilters() {
        when(geocodingClient.geocode("서울시 종로구 1-1")).thenReturn(geocoded("11110"));
        when(repository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));
        when(repository.search("11110", ConsentStatus.CONSENTED, PageRequest.of(0, 20)))
                .thenReturn(new PageImpl<>(List.of(profile()), PageRequest.of(0, 20), 1));

        var created = service.register(new ElderlyRegisterRequest("김안심", "010", "서울시 종로구 1-1", ConsentStatus.CONSENTED, null, null));
        var listed = service.list("11110", ConsentStatus.CONSENTED, PageRequest.of(0, 20));

        assertThat(created.regionCode()).isEqualTo("11110");
        assertThat(listed.totalElements()).isEqualTo(1);
        verify(repository).save(any(ElderlyProfile.class));
    }

    @Test
    void updatesAddressAndConsentAndRejectsMissingProfile() {
        ElderlyProfile profile = profile();
        when(repository.findById(1L)).thenReturn(Optional.of(profile));
        when(repository.findById(99L)).thenReturn(Optional.empty());
        when(geocodingClient.geocode("서울시 마포구 2-2")).thenReturn(geocoded("11440"));

        var updated = service.update(1L, new ElderlyUpdateRequest(null, null, "서울시 마포구 2-2", ConsentStatus.WITHDRAWN, null, null));

        assertThat(updated.address()).isEqualTo("서울시 마포구 2-2");
        assertThat(updated.consentStatus()).isEqualTo(ConsentStatus.WITHDRAWN);
        assertThatThrownBy(() -> service.getById(99L)).isInstanceOf(BusinessException.class);
    }

    @Test
    void deletesAProfileThatHasNoInterventionHistory() {
        ElderlyProfile profile = profile();
        when(repository.findById(1L)).thenReturn(Optional.of(profile));

        service.delete(1L);

        verify(repository).delete(profile);
    }

    @Test
    void rejectsDeletionOfAProfileThatDoesNotExist() {
        when(repository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.delete(99L))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.RESOURCE_NOT_FOUND));
    }

    @Test
    void reportsAConflictWhenTheProfileIsStillReferencedByInterventionHistory() {
        when(repository.findById(1L)).thenReturn(Optional.of(profile()));
        doThrow(new DataIntegrityViolationException("fk")).when(repository).flush();

        assertThatThrownBy(() -> service.delete(1L))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.CONFLICT));
    }

    private GeocodingResult geocoded(String regionCode) {
        return new GeocodingResult(new BigDecimal("37.5730000"), new BigDecimal("126.9794000"), regionCode);
    }

    private ElderlyProfile profile() {
        return ElderlyProfile.builder().displayName("김안심").phone("010").address("서울시 종로구 1-1")
                .latitude(new BigDecimal("37.5730000")).longitude(new BigDecimal("126.9794000"))
                .regionCode("11110").consentStatus(ConsentStatus.CONSENTED).build();
    }

    @Test
    void registersAndUpdatesHealthInformation() {
        when(geocodingClient.geocode("서울시 종로구 1-1")).thenReturn(geocoded("11110"));
        when(repository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));
        ElderlyProfile profile = profile();
        when(repository.findById(1L)).thenReturn(Optional.of(profile));

        var created = service.register(new ElderlyRegisterRequest("김안심", "010", "서울시 종로구 1-1",
                ConsentStatus.CONSENTED, LocalDate.of(1950, 3, 1), "고혈압, 당뇨"));
        var updated = service.update(1L, new ElderlyUpdateRequest(null, null, null, null,
                LocalDate.of(1948, 7, 20), "거동 불편"));

        assertThat(created.age()).isNotNull();
        assertThat(created.healthNote()).isEqualTo("고혈압, 당뇨");
        assertThat(updated.healthNote()).isEqualTo("거동 불편");
    }
}
