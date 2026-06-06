C FILE: FIBONACCI.F
C Loosely based on the pyfort example by Lars Buntemeyer (MIT licence)
C https://github.com/larsbuntemeyer/pyfort
      SUBROUTINE FIB(A, N)
C     Calculate first N Fibonacci numbers
      INTEGER N
      REAL*8 A(N)
      DO I = 1, N
         IF (I .EQ. 1) THEN
            A(I) = 0.0D0
         ELSEIF (I .EQ. 2) THEN
            A(I) = 1.0D0
         ELSE
            A(I) = A(I-1) + A(I-2)
         ENDIF
      ENDDO
      END
C END FILE FIBONACCI.F
