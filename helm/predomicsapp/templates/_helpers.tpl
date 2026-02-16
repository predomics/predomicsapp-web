{{/*
PredomicsApp Helm Chart — Template Helpers
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "predomicsapp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "predomicsapp.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label.
*/}}
{{- define "predomicsapp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "predomicsapp.labels" -}}
helm.sh/chart: {{ include "predomicsapp.chart" . }}
{{ include "predomicsapp.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "predomicsapp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "predomicsapp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Secret name — use existing secret or generate one.
*/}}
{{- define "predomicsapp.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "predomicsapp.fullname" . }}
{{- end }}
{{- end }}

{{/*
Database URL — either external or built from bundled PostgreSQL.
*/}}
{{- define "predomicsapp.databaseUrl" -}}
{{- if .Values.externalDatabase.url }}
{{- .Values.externalDatabase.url }}
{{- else }}
{{- printf "postgresql+asyncpg://%s:$(POSTGRES_PASSWORD)@%s-postgresql:5432/%s" .Values.postgresql.auth.username (include "predomicsapp.fullname" .) .Values.postgresql.auth.database }}
{{- end }}
{{- end }}
