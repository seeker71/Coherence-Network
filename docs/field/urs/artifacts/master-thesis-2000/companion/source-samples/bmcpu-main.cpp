#define INITGUID

#include <bmvm.h>
#include <stdio.h>
#include <stdlib.h>

DEFINE_GUID( TEST_def, 0x63CC7777, 0xD99A, 0x11d3, 0xA5, 0x49, 0x00, 0x10, 0x5A, 0xAB, 0x8B, 0x48 );



void main( void ) {
   BMVM pCPU;

   BMCreateMachine( &pCPU, 0 );
//   BMLoad( pCPU, T( "D:\\Work\\Projects\\Angelic\\Test\\BML.lang" ));
//   BMREF hRef, hGuidRef;
//   BMQueryRefByName( &pCPU, T( "BML.lang.Test$Def" ), &hRef );
//   BMObjectGetFixed( &pCPU, &hRef, 1, &hGuidRef );
//   GUID* hGUID;
//   DWORD iSize = sizeof( *hGUID );
//   BMObjectBinaryData( &pCPU, ()&hGuidRef, &hGUID, &iSize );
   BMStartApplication( pCPU, &TEST_def );
   BMMachineStep( pCPU, BM_RUN );

/*
   BMTest( pCPU, 1 );
   do {
      UNICHAR szBuffer[1024];
      BMVM_STATE sState;
      sState.dwSize = sizeof( BMVM_STATE );
      BMQueryMachineState( pCPU, &sState );
      PUNICHAR szMode = sState.byMode ? L"UNDO" : L"  DO";
      if( BMQueryInstruction( pCPU, sState.ndxCodeOffset, szBuffer, 1024 ) == BM_SUCCESS ) {
         wprintf( L"%s: %s\n", szMode, szBuffer );
      }
   } while( BMMachineStep( pCPU, BM_STEP_INTO ) == BM_SUCCESS );
   BMDestroyMachine( pCPU, 0 );
*/
}
