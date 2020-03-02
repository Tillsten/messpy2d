// DLL initialization and comm functions
long			C843_Connect(long iBoardNumber);
BOOL		C843_IsConnected(long iID);
BOOL	  C843_ListPCI(char* szIDList,long maxlen);
void		C843_CloseConnection(long iID);
long			C843_GetError(long iID);
BOOL		C843_SetErrorCheck(long iID, BOOL bErrorCheck);
BOOL		C843_TranslateError(long errNr, char* szBuffer, long maxlen);
long			C843_GetCurrentBoardId(long iBoardNumber);




/////////////////////////////////////////////////////////////////////////////
// general

BOOL  C843_qHLP(const long iID, char* buffer, long maxlen);
BOOL  C843_qHPA(const long iID, char* buffer, long maxlen);
BOOL  C843_qHDR(const long iID, char* buffer, long maxlen);
BOOL  C843_qERR(long iID, long* pnError);
BOOL  C843_qIDN(long iID, char* buffer, long maxlen);
BOOL  C843_qVER(long iID, char* buffer, long maxlen);
BOOL  C843_INI(long iID, const char* szAxes);
BOOL  C843_CLR(long iID, const char* szAxes);

/////////////////////////////////////////////////////////////////////////////
// motion, monitoring
BOOL  C843_MOV(long iID, const char* szAxes, const double* pdValarray);
BOOL  C843_qMOV(long iID, const char* szAxes, double* pdValarray);
BOOL  C843_MVR(long iID, const char* szAxes, const double* pdValarray);
BOOL  C843_MVE(long iID, const char* szAxes, const double* pdValarray);
BOOL  C843_IsMoving(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_IsUserProfileActive(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_qONT(long iID, const char* szAxes, BOOL* pbValarray);

BOOL  C843_qPOS(long iID, const char* szAxes, double* pdValarray);
BOOL  C843_POS(long iID, const char* szAxes, const double* pdValarray);

BOOL  C843_DFF(long iID, const char* szAxes, const double* pdValarray);
BOOL  C843_qDFF(long iID, const char* szAxes, double* pdValarray);

BOOL  C843_DFH(long iID, const char* szAxes);
BOOL  C843_qDFH(long iID, const char* szAxes, double* pdValarray);
BOOL  C843_GOH(long iID, const char* szAxes);

BOOL  C843_HLT(long iID, const char* szAxes);
BOOL  C843_STP(long iID);

BOOL  C843_SVO(long iID, const char* szAxes, const BOOL* pbValarray);
BOOL  C843_qSVO(long iID, const char* szAxes, BOOL* pbValarray);

BOOL  C843_SMO(long iID, const char* szAxes, const long* pnValarray);
BOOL  C843_qSMO(long iID, const char* szAxes, long* pnValarray);

BOOL  C843_VEL(long iID, const char* szAxes, const double* pdValarray);
BOOL  C843_qVEL(long iID, const char* szAxes, double* pdValarray);
BOOL  C843_ACC(long iID, const char* szAxes, const double* pdValarray);
BOOL  C843_qACC(long iID, const char* szAxes, double* pdValarray);
BOOL  C843_DEC(long iID, const char* szAxes, const double* pdValarray);
BOOL  C843_qDEC(long iID, const char* szAxes, double* pdValarray);

BOOL  C843_qSRG(long iID, const char* szAxes, const long* iCmdarray, long* iValarray);

BOOL  C843_BRA(long iID, const char* szAxes, const BOOL* pbValarray);
BOOL  C843_qBRA(long iID, char* szBuffer, const long maxlen);

/////////////////////////////////////////////////////////////////////////////
// stages assignment, parameters
BOOL  C843_qCST(long iID, const char* szAxes, char* names,  long maxlen);
BOOL  C843_CST(long iID, const char* szAxes, const char* names);
BOOL  C843_qVST(long iID, char* buffer,  long maxlen);
BOOL  C843_qTVI(long iID, char* axes,  long maxlen);
BOOL  C843_SAI(long iID, const char* szOldAxes, const char* szNewAxes);
BOOL  C843_qSAI(long iID, char* axes,  long maxlen);
BOOL  C843_qSAI_ALL(long iID, char* axes,  long maxlen);
BOOL  C843_SPA(long iID, const char* szAxes, const long* iCmdarray, const double* dValarray, const char* szStageNames);
BOOL  C843_qSPA(long iID, const char* szAxes, const long* iCmdarray, double* dValarray, char* szStageNames, long iMaxNameSize);

/////////////////////////////////////////////////////////////////////////////
// Trigger Output
BOOL  C843_CTO(long iID, const long* iTriggerLinesArray, const long* iParamIDArray,  const char* szValues, long iArraySize);
BOOL  C843_qCTO(long iID, const long* iTriggerLinesArray, const long* pParamIDArray, char* szBuffer, long iArraySize, long iBufferMaxlen);
BOOL  C843_TRO(long iID,  const long* iTriggerLinesArray, const BOOL* pbValarray, long iArraySize);
BOOL  C843_qTRO(long iID, const long* iTriggerLinesArray, BOOL* pbValarray, long iArraySize);

/////////////////////////////////////////////////////////////////////////////
// Digital I/O
BOOL  C843_GetInputChannelNames(long iID, char* szBuffer, const long maxlen);
BOOL  C843_GetOutputChannelNames(long iID, char* szBuffer, const long maxlen);
BOOL  C843_DIO(long iID, const char* szChannels, const BOOL* pbValarray);
BOOL  C843_qDIO(long iID, const char* szChannels, BOOL* pbValarray);
BOOL  C843_qTIO(long iID, long* pINr, long* pONr);


/////////////////////////////////////////////////////////////////////////////
// String commands

BOOL  C843_C843Commandset(long iID, const char* szCommand, char* szAwnser, long iMaxSize);

BOOL  C843_GcsCommandset(long iID, const char* szCommand);
BOOL  C843_GcsGetAnswer(long iID, char* szAnswer, long bufsize);
BOOL  C843_GcsGetAnswerSize(long iID, long* iAnswerSize);



/////////////////////////////////////////////////////////////////////////////
// QMC commands.
BOOL  C843_SetQMC(long iID, uint8_t bCmd, uint8_t bAxis, int32_t Param);
BOOL  C843_GetQMC(long iID, uint8_t bCmd, uint8_t bAxis, int32_t* pResult);
BOOL  C843_SetQMCA(long iID, uint8_t bCmd, uint8_t bAxis, uint16_t Param1, int32_t lParam2);
BOOL  C843_GetQMCA(long iID, uint8_t bCmd, uint8_t bAxis, uint16_t lParam, int32_t* pResult);


/////////////////////////////////////////////////////////////////////////////
// limits, referencing
BOOL  C843_MNL(long iID,  const char* szAxes);
BOOL  C843_MPL(long iID,  const char* szAxes);
BOOL  C843_REF(long iID, const char* szAxes);
BOOL  C843_FRF(long iID, const char* szAxes);
BOOL  C843_FPL(long iID, const char* szAxes);
BOOL  C843_FNL(long iID, const char* szAxes);
BOOL  C843_FED(long iID, const char* szAxes, const long* iEdgeIDArray, const long* iParArray);
BOOL  C843_qFED(long iID, const char* szAxes, long* iEdgeIDArray, long* iParArray);
BOOL  C843_qFES(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_qREF(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_qFRF(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_qLIM(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_IsReferencing(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_IsControllerReady(const long ID, long* piControllerReady);
BOOL  C843_GetRefResult(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_IsReferenceOK(long iID, const char* szAxes, BOOL* pbValarray);
BOOL  C843_qTMN(long iID, const char* szAxes, double* pdValarray);
BOOL  C843_qTMX(long iID, const char* szAxes, double* pdValarray);
BOOL  C843_RON(long iID, const char* szAxes, const BOOL* pbValarray);
BOOL  C843_qRON(long iID, const char* szAxes, BOOL* pbValarray);


/////////////////////////////////////////////////////////////////////////////
// User Profile Mode
BOOL  C843_UPB(long iID, const char* szClusters, const long* iCmdarray, const long* iPararray, const long* iValarray);
BOOL  C843_UPD(long iID, const char* szClusters, const long* iCmdarray, const long* iPararray, const double* dValarray);
BOOL  C843_UPC(long iID, const char* szAxes,	const char* szClusters, const long* iCmdarray, const long* iPararray);
BOOL  C843_UPA(long iID, const char* szClusters, const long* iCmdarray);
BOOL  C843_UPR(long iID, const char* szAxes,	const char* szClusters, const long* iCmdarray);
BOOL  C843_qUPB(long iID,const char* szClusters, const long* iCmdarray, const long* iPararray, long* iValarray);
BOOL  C843_qUPD(long iID,const char* szClusters, const long* iCmdarray, const long* iPararray, double* dValarray);
BOOL  C843_qUPC(long iID,char* szClusters,char* szAxes, long* iCmdarray, long* iPararray);
BOOL  C843_qUPA(long iID,const char* szClusters, const long* iCmdarray, long* iPararray);


//////////////////////////////////////////////////////////////////////////////
// Trace
BOOL  C843_STE(long iID, char cAxis, double dOffset);
BOOL  C843_qSTE(long iID, char cAxis, long iOffset, long nrValues, double* pdValarray);
BOOL  C843_DRC(long iID, const long* iRecTableId, const char* sRecSourceId, const long* iRecOption, const long* TriggerOption);
BOOL  C843_qDRC(long iID, const long* iRecTableId, char* sRecSourceId, long* iRecOption, long* TriggerOption, long iArraySize);
BOOL  C843_qDRL(long iID, long* nrValues);
BOOL  C843_DRT(long iID, const long* iRecTableId, const long* TriggerOption, const char* sValue, long iArrayLength);
BOOL  C843_qDRT(long iID, const long* iRecTableId,  long* TriggerOption, char* sValue, long iArraySize, long iValueBufferLength);
BOOL  C843_qDRR_SYNC(long iID, long iRecTableId, long iOffset, long nrValues, double* pdValArray);
BOOL  C843_qDRR(long iID, const long* piRecTableIds, long iNumberOfRecChannels, long iOffset, long nrValues, double** pdValArray, char* szGcsArrayHeader, long iGcsArrayHeaderMaxSize);
long  C843_GetAsyncBufferIndex(long iID);
BOOL 	C843_GetAsyncBuffer(long iID, double** pdValueArray);
BOOL  C843_qTNR(long iID, long* iNrOfTables);
BOOL  C843_RTR(long iID, long iRecordTableRate);
BOOL  C843_qRTR(long iID, long* iRecordTableRate);

/////////////////////////////////////////////////////////////////////////////
// Special
BOOL		C843_AddStage(long iID, const char* szAxes);
BOOL		C843_RemoveStage(long iID, const char* szStageName);
BOOL	 C843_OpenUserStagesEditDialog(long iID);
BOOL	 C843_OpenPiStagesEditDialog(long iID);

/////////////////////////////////////////////////////////////////////////////
// Joystick
BOOL  C843_JON(long iId,const long* iJoystickIDsArray, const BOOL* pbValueArray, long iArraySize);
BOOL  C843_qJON(long iID, const long* iJoystickIDsArray, BOOL* pbValueArray, long iArraySize);
BOOL  C843_qJAX(long iId, const long* iJoystickIDsArray, const long* iAxesIDsArray, long iArraySize, char* szAxesBuffer, long iBufferSize);
BOOL  C843_JAX(long iID,  long iJoystickID,  long iAxesID, const char* szAxesBuffer);

/////////////////////////////////////////////////////////////////////////////
// electronic gearing commands
BOOL  C843_SRA(long iID, const char* szAxes, double* dValArray);
BOOL  C843_qSRA(long iID, const char* szAxes, double* dValArray);
BOOL  C843_EGE(long iID, const char* szAxes, BOOL* bValueArray);
BOOL  C843_qEGE(long iID, const char* szAxes, BOOL* bValueArray);
BOOL  C843_MAS(long iID, const char* szAxes, const char* szMasters);
BOOL  C843_qMAS(long iID, const char* szAxes, char* szMasters);

///////////////////////////////////////////////////////////////////////////////
// for internal use
BOOL  C843_DisableSingleStagesDatFiles(long iID,BOOL bDisable);
BOOL  C843_DisableUserStagesDatFiles(long iID,BOOL bDisable);

