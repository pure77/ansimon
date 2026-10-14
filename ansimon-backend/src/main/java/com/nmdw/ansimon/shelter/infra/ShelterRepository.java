package com.nmdw.ansimon.shelter.infra;

import com.nmdw.ansimon.shelter.domain.Shelter;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ShelterRepository extends JpaRepository<Shelter, Long> {
}
